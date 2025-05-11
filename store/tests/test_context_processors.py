from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from unittest.mock import patch
from decimal import Decimal

from store.models import Category, Cart, CartItem, Product, Notification
from store.context_processors import categories, cart_processor, notifications_processor

class ContextProcessorsTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword'
        )
        
        # Create some categories
        self.category1 = Category.objects.create(name='Category 1', slug='category-1')
        self.category2 = Category.objects.create(name='Category 2', slug='category-2')
        
        # Create a product
        self.product = Product.objects.create(
            name='Test Product',
            slug='test-product',
            description='Test description',
            price=Decimal('10.00'),
            category=self.category1,
            stock=10,
            is_active=True
        )
        
        # Create a cart for the user
        self.cart = Cart.objects.create(user=self.user)
        self.cart_item = CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            quantity=2
        )
        
        # Create a notification for the user
        self.notification = Notification.objects.create(
            user=self.user,
            message='Test notification',
            is_read=False
        )
    
    def _get_request(self, authenticated=True):
        """Helper method to create a request object"""
        request = self.factory.get('/')
        
        # Add session to request
        middleware = SessionMiddleware(lambda x: None)
        middleware.process_request(request)
        request.session.save()
        
        # Add user or anonymous user to request
        if authenticated:
            request.user = self.user
        else:
            request.user = User()
            request.user.is_authenticated = False
            
        return request
    
    def test_categories_processor(self):
        """Test the categories context processor"""
        request = self._get_request()
        context = categories(request)
        
        self.assertIn('categories', context)
        self.assertEqual(list(context['categories']), [self.category1, self.category2])
    
    def test_cart_processor_authenticated(self):
        """Test the cart processor for an authenticated user"""
        request = self._get_request(authenticated=True)
        context = cart_processor(request)
        
        self.assertIn('cart', context)
        self.assertEqual(context['cart'], self.cart)
        self.assertEqual(context['cart_items_count'], 2)
    
    def test_cart_processor_unauthenticated_with_session(self):
        """Test the cart processor for an unauthenticated user with session"""
        request = self._get_request(authenticated=False)
        
        # Create a cart for the session
        session_cart = Cart.objects.create(session_id=request.session.session_key)
        CartItem.objects.create(
            cart=session_cart,
            product=self.product,
            quantity=1
        )
        
        context = cart_processor(request)
        
        self.assertIn('cart', context)
        self.assertEqual(context['cart'], session_cart)
        self.assertEqual(context['cart_items_count'], 1)
    
    def test_cart_processor_no_cart(self):
        """Test the cart processor when no cart exists"""
        # Create a new user without a cart
        user = User.objects.create_user(
            username='newuser',
            email='new@example.com',
            password='newpassword'
        )
        
        request = self._get_request(authenticated=False)
        request.user = user
        
        context = cart_processor(request)
        
        self.assertIn('cart', context)
        self.assertIsNone(context['cart'])
        self.assertEqual(context['cart_items_count'], 0)
    
    def test_notifications_processor_authenticated(self):
        """Test the notifications processor for an authenticated user"""
        request = self._get_request(authenticated=True)
        context = notifications_processor(request)
        
        self.assertIn('notifications', context)
        self.assertEqual(list(context['notifications']), [self.notification])
        self.assertEqual(context['unread_notifications_count'], 1)
    
    def test_notifications_processor_unauthenticated(self):
        """Test the notifications processor for an unauthenticated user"""
        request = self._get_request(authenticated=False)
        context = notifications_processor(request)
        
        self.assertIn('notifications', context)
        self.assertEqual(list(context['notifications']), [])
        self.assertEqual(context['unread_notifications_count'], 0)
    
    def test_notifications_processor_exception_handling(self):
        """Test the notifications processor handles exceptions gracefully"""
        request = self._get_request(authenticated=True)
        
        # Simulate a database error
        with patch('store.models.Notification.objects.filter') as mock_filter:
            mock_filter.side_effect = Exception("Database error")
            
            # Should not raise an exception
            context = notifications_processor(request)
            
            self.assertIn('notifications', context)
            self.assertEqual(list(context['notifications']), [])
            self.assertEqual(context['unread_notifications_count'], 0) 