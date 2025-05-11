from social_core.pipeline.user import create_user as social_create_user
from django.contrib.auth.models import User
from django.utils.crypto import get_random_string
from store.models import UserProfile, Notification
import logging
import random
import string
from social_django.models import UserSocialAuth

logger = logging.getLogger(__name__)

def generate_secure_password(email=None, length=16):
    """Generate a secure random password or use email as base"""
    if email and random.choice([True, False]):
        # Use email as base password (50% chance)
        # Add some random characters for security
        email_base = email.split('@')[0]
        random_suffix = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=6))
        return f"{email_base}_{random_suffix}"
    else:
        # Generate completely random password
        chars = string.ascii_letters + string.digits + string.punctuation
        return ''.join(random.choices(chars, k=length))

def create_user(strategy, details, backend, user=None, *args, **kwargs):
    """
    Custom pipeline function to create a user with proper profile information 
    from OAuth providers like Google.
    """
    if user:
        # If user already exists, ensure they are active
        if not user.is_active:
            user.is_active = True
            user.save()
            
            # Update the profile to mark as verified
            try:
                profile = UserProfile.objects.get(user=user)
                profile.is_email_verified = True
                profile.save()
                
                # Create notification about account activation
                Notification.objects.create(
                    user=user,
                    title="Account Activated",
                    message="Your account has been activated automatically because you signed in with Google.",
                    link="/profile/",
                    is_read=False
                )
                logger.info(f"User {user.username} activated via Google sign-in")
            except UserProfile.DoesNotExist:
                logger.error(f"Profile does not exist for user {user.username}")
        
        return {'is_new': False, 'user': user}
        
    # Extract user information from the OAuth response
    email = details.get('email')
    first_name = details.get('first_name', '')
    last_name = details.get('last_name', '')
    
    if not email:
        # If no email is provided, we can't create a user
        logger.warning("No email provided by OAuth provider, cannot create user")
        return None
        
    # Check if user already exists with this email
    try:
        existing_user = User.objects.get(email=email)
        # Existing user found, make sure they're active
        if not existing_user.is_active:
            existing_user.is_active = True
            existing_user.save()
            
            # Update their profile
            try:
                profile = UserProfile.objects.get(user=existing_user)
                profile.is_email_verified = True
                profile.save()
                
                # Create notification about account activation
                Notification.objects.create(
                    user=existing_user,
                    title="Account Activated",
                    message="Your account has been activated automatically because you signed in with Google.",
                    link="/profile/",
                    is_read=False
                )
                logger.info(f"User {existing_user.username} activated via Google sign-in")
            except UserProfile.DoesNotExist:
                logger.error(f"Profile does not exist for user {existing_user.username}")
        
        return {
            'is_new': False,
            'user': existing_user
        }
    except User.DoesNotExist:
        pass
    
    # Generate a unique username based on email prefix
    username = email.split('@')[0]
    
    # Check if username exists and make it unique if needed
    if User.objects.filter(username=username).exists():
        username = f"{username}_{get_random_string(5)}"
    
    # Generate a secure password
    password = generate_secure_password(email)
        
    # Create the user with the generated password
    user = strategy.create_user(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=password,
        is_active=True,
    )
    
    # Create user profile in the correct table
    UserProfile.objects.create(
        user=user,
        role='customer',
        is_email_verified=True  # Auto-verify for social login
    )
    
    # Create notification with password information
    notification_message = f"Welcome! You've signed up with Google. Your temporary password is: {password}. Please update it in your profile settings for security reasons."
    
    try:
        Notification.objects.create(
            user=user,
            title="Welcome to E-Shop",
            message=notification_message,
            link="/profile/", # Link to profile page where they can change password
            is_read=False
        )
        logger.info(f"Password notification created for user {username}")
    except Exception as e:
        logger.error(f"Error creating notification for user {username}: {str(e)}")
    
    logger.info(f"Created new user {username} via OAuth2")
    
    return {
        'is_new': True,
        'user': user
    }

def associate_by_email(strategy, details, backend, user=None, *args, **kwargs):
    """
    Associate current auth with a user with the same email address in the DB.
    This pipeline entry is not 100% secure unless you know that the providers
    enabled enforce email verification on their side.
    """
    if user:
        return None
        
    # Check if social auth already exists for this UID
    uid = kwargs.get('uid')
    provider = backend.name
    
    if uid and provider:
        try:
            # Check if we already have this social auth user
            social_user = UserSocialAuth.objects.get(provider=provider, uid=uid)
            try:
                # Make sure the associated user actually exists
                if social_user.user:
                    return {'user': social_user.user, 'is_new': False}
            except User.DoesNotExist:
                # If the user doesn't exist, clean up the orphaned social auth entry
                logger.warning(f"Found orphaned social auth entry for {provider}:{uid}. Deleting it.")
                social_user.delete()
        except UserSocialAuth.DoesNotExist:
            pass
    
    # If no social auth exists, try to find a user with matching email
    email = details.get('email')
    if email:
        # Try to associate accounts registered with the same email address
        users = list(User.objects.filter(email=email))
        if len(users) == 0:
            return None
        elif len(users) > 1:
            # Handle multiple users with same email - use the first one
            logger.warning(f"Multiple users found with email {email}")
            return {'user': users[0], 'is_new': False}
        else:
            user = users[0]
            return {'user': user, 'is_new': False}
    return None

def get_profile_picture(strategy, details, response, backend, uid, user, *args, **kwargs):
    """
    Get the profile picture from the OAuth provider and save it to the user's profile.
    """
    if not user:
        return
        
    # Get profile picture URL from OAuth response (Google)
    if backend.name == 'google-oauth2':
        if 'picture' in response:
            picture_url = response.get('picture')
            
            # Make sure the user has a profile in the correct table
            try:
                # Try to get the UserProfile from the store app
                profile, created = UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'role': 'customer',
                        'is_email_verified': True
                    }
                )
                
                # Store avatar URL if the model has this field
                if hasattr(profile, 'avatar_url'):
                    profile.avatar_url = picture_url
                    profile.save()
                    logger.info(f"Updated profile picture for user {user.username}")
            except Exception as e:
                logger.error(f"Error updating profile picture for user {user.username}: {str(e)}")
    
    return 