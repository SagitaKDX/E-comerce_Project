from django.test import TestCase
from django.contrib.auth.models import User
from unittest.mock import MagicMock, patch
import logging

from store.models import UserProfile
from store.social_auth import create_user, associate_by_email, get_profile_picture

class SocialAuthTest(TestCase):
    def setUp(self):
        # Create a test user
        self.existing_user = User.objects.create_user(
            username='existinguser',
            email='existing@example.com',
            password='testpassword'
        )
        
        # Create user profile
        self.profile = UserProfile.objects.create(
            user=self.existing_user,
            role='customer',
            is_email_verified=False
        )
        
        # Mock strategy
        self.strategy = MagicMock()
        self.strategy.create_user = MagicMock(return_value=User(
            username='newuser',
            email='new@example.com',
            first_name='New',
            last_name='User'
        ))
        
        # Mock backend
        self.backend = MagicMock()
        self.backend.name = 'google-oauth2'
        
    def test_create_user_returns_existing_user(self):
        """Test that create_user returns an existing user if provided"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword'
        )
        
        result = create_user(
            strategy=self.strategy,
            details={},
            backend=self.backend,
            user=user
        )
        
        self.assertEqual(result['is_new'], False)
        self.assertEqual(result['user'], user)
        
    def test_create_user_with_no_email(self):
        """Test create_user with no email in details"""
        result = create_user(
            strategy=self.strategy,
            details={},  # No email
            backend=self.backend,
            user=None
        )
        
        self.assertIsNone(result)
        
    def test_create_user_with_existing_email(self):
        """Test create_user with an email that matches an existing user"""
        result = create_user(
            strategy=self.strategy,
            details={'email': 'existing@example.com'},
            backend=self.backend,
            user=None
        )
        
        self.assertEqual(result['is_new'], False)
        self.assertEqual(result['user'], self.existing_user)
        
    def test_create_new_user(self):
        """Test create_user creates a new user"""
        result = create_user(
            strategy=self.strategy,
            details={
                'email': 'new@example.com',
                'first_name': 'New',
                'last_name': 'User'
            },
            backend=self.backend,
            user=None
        )
        
        self.assertEqual(result['is_new'], True)
        self.strategy.create_user.assert_called_once_with(
            username='new',
            email='new@example.com',
            first_name='New',
            last_name='User',
            is_active=True
        )
        
        # Check that a profile was created
        user = result['user']
        profile_exists = UserProfile.objects.filter(user=user).exists()
        self.assertTrue(profile_exists)
        
    def test_create_user_with_existing_username(self):
        """Test create_user with an email that would generate an existing username"""
        # Create a user with username 'new'
        User.objects.create_user(
            username='new',
            email='other@example.com',
            password='testpassword'
        )
        
        # This should add a random string to the username
        with patch('store.social_auth.get_random_string', return_value='12345'):
            result = create_user(
                strategy=self.strategy,
                details={'email': 'new@example.com'},
                backend=self.backend,
                user=None
            )
            
            self.strategy.create_user.assert_called_once()
            call_args = self.strategy.create_user.call_args[1]
            self.assertEqual(call_args['username'], 'new_12345')
            
    def test_associate_by_email_with_user(self):
        """Test associate_by_email returns None if user is provided"""
        result = associate_by_email(
            strategy=self.strategy,
            details={},
            backend=self.backend,
            user=self.existing_user
        )
        
        self.assertIsNone(result)
        
    def test_associate_by_email_with_no_email(self):
        """Test associate_by_email returns None if no email is provided"""
        result = associate_by_email(
            strategy=self.strategy,
            details={},  # No email
            backend=self.backend,
            user=None
        )
        
        self.assertIsNone(result)
        
    def test_associate_by_email_with_existing_email(self):
        """Test associate_by_email with an email that matches an existing user"""
        result = associate_by_email(
            strategy=self.strategy,
            details={'email': 'existing@example.com'},
            backend=self.backend,
            user=None
        )
        
        self.assertEqual(result['is_new'], False)
        self.assertEqual(result['user'], self.existing_user)
        
    def test_associate_by_email_with_multiple_users(self):
        """Test associate_by_email with an email that matches multiple users"""
        # Create another user with the same email (should never happen in production)
        User.objects.create_user(
            username='anothertestuser',
            email='existing@example.com',  # Same email as existing_user
            password='testpassword'
        )
        
        with self.assertLogs(level='WARNING'):
            result = associate_by_email(
                strategy=self.strategy,
                details={'email': 'existing@example.com'},
                backend=self.backend,
                user=None
            )
            
            self.assertEqual(result['is_new'], False)
            # Should return the first user found
            self.assertEqual(result['user'].username, 'existinguser')
            
    def test_get_profile_picture_no_user(self):
        """Test get_profile_picture does nothing if no user is provided"""
        result = get_profile_picture(
            strategy=self.strategy,
            details={},
            response={},
            backend=self.backend,
            uid='12345',
            user=None
        )
        
        self.assertIsNone(result)
        
    def test_get_profile_picture_with_picture(self):
        """Test get_profile_picture with a picture in the response"""
        # Add the avatar_url field to UserProfile for this test
        UserProfile.avatar_url = MagicMock()
        
        response = {
            'picture': 'https://example.com/picture.jpg'
        }
        
        result = get_profile_picture(
            strategy=self.strategy,
            details={},
            response=response,
            backend=self.backend,
            uid='12345',
            user=self.existing_user
        )
        
        # Should have tried to update the profile
        self.assertIsNone(result)
        
    def test_get_profile_picture_with_non_google_backend(self):
        """Test get_profile_picture with a non-Google backend"""
        backend = MagicMock()
        backend.name = 'facebook'  # Not google-oauth2
        
        result = get_profile_picture(
            strategy=self.strategy,
            details={},
            response={'picture': 'https://example.com/picture.jpg'},
            backend=backend,
            uid='12345',
            user=self.existing_user
        )
        
        # Should do nothing
        self.assertIsNone(result) 