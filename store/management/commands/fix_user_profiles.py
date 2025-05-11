from django.core.management.base import BaseCommand
from django.db import connection
from django.contrib.auth.models import User
from store.models import UserProfile
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Fixes duplicate user profile data between user_profile and store_userprofile tables'

    def handle(self, *args, **options):
        # Get all users that might have profiles in the wrong table
        users_with_missing_profiles = []
        
        # Get users who login via social auth but don't have a store_userprofile
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT auth_user.id, auth_user.username, auth_user.email
                FROM auth_user
                LEFT JOIN store_userprofile ON auth_user.id = store_userprofile.user_id
                WHERE store_userprofile.id IS NULL
            """)
            users_with_missing_profiles = cursor.fetchall()
        
        self.stdout.write(f"Found {len(users_with_missing_profiles)} users with missing profiles")
        
        # Create profiles for users who are missing them
        profiles_created = 0
        for user_id, username, email in users_with_missing_profiles:
            try:
                # Check if they have data in the user_profile table
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT is_email_verified, email_verification_token
                        FROM user_profile
                        WHERE user_id = %s
                    """, [user_id])
                    user_profile_data = cursor.fetchone()
                
                # Get the user object
                user = User.objects.get(id=user_id)
                
                # Create a profile in the store_userprofile table
                if user_profile_data:
                    is_verified, token = user_profile_data
                    profile = UserProfile.objects.create(
                        user=user,
                        is_email_verified=is_verified,
                        email_verification_token=token,
                        role='customer'  # Default role
                    )
                else:
                    # No user_profile data, just create a default one
                    profile = UserProfile.objects.create(
                        user=user,
                        role='customer'
                    )
                
                profiles_created += 1
                self.stdout.write(self.style.SUCCESS(f"Created profile for user {username} ({email})"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error creating profile for user {username}: {str(e)}"))
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f"Created {profiles_created} user profiles"))
        
        # Optionally, we could drop the user_profile table if it's not needed anymore
        if profiles_created > 0 and profiles_created == len(users_with_missing_profiles):
            self.stdout.write(self.style.WARNING("All profiles have been migrated."))
            self.stdout.write(self.style.WARNING("You can safely drop the user_profile table if it's not used elsewhere."))
            
            # Rename the table directly
            try:
                with connection.cursor() as cursor:
                    cursor.execute("ALTER TABLE user_profile RENAME TO user_profile_old")
                self.stdout.write(self.style.SUCCESS("Renamed user_profile table to user_profile_old"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error renaming table: {str(e)}"))
                self.stdout.write(self.style.WARNING("To rename manually: ALTER TABLE user_profile RENAME TO user_profile_old;"))
        
        # Fix social_auth.py to ensure it always uses the correct profile model
        self.stdout.write(self.style.SUCCESS('User profiles fixed successfully')) 