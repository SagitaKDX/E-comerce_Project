from django.test import TestCase
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
import tempfile
import os

from store.models import (
    UserProfile, Category, Product, Comment, 
    CommentResponse, Cart, CartItem, Order, 
    ShippingAddress, CreditCard, Notification
)

class UserProfileModelTest(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword'
        )
        # Create user profile
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='customer',
            is_email_verified=False,
            email_verification_token='test-token'
        )
        
    def test_profile_creation(self):
        """Test UserProfile model creation"""
        self.assertEqual(self.profile.user.username, 'testuser')
        self.assertEqual(self.profile.role, 'customer')
        self.assertFalse(self.profile.is_email_verified)
        self.assertEqual(self.profile.email_verification_token, 'test-token')
        
    def test_string_representation(self):
        """Test UserProfile string representation"""
        self.assertEqual(str(self.profile), "testuser's profile")
        
    def test_is_csr_method(self):
        """Test is_csr method"""
        # Default customer role
        self.assertFalse(self.profile.is_csr())
        
        # Update to CSR role
        self.profile.role = 'csr'
        self.profile.save()
        self.assertTrue(self.profile.is_csr())
        
        # Staff user
        self.user.is_staff = True
        self.user.save()
        self.profile.role = 'customer'  # Even with customer role
        self.profile.save()
        self.assertTrue(self.profile.is_csr())  # Should be True because user is staff

    def test_is_crm_user_method(self):
        """Test is_crm_user method"""
        # Default customer role
        self.assertFalse(self.profile.is_crm_user())
        
        # Update to CRM user role
        self.profile.role = 'crm_user'
        self.profile.save()
        self.assertTrue(self.profile.is_crm_user())

class CategoryModelTest(TestCase):
    def setUp(self):
        # Create test category
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )
        
    def test_category_creation(self):
        """Test Category model creation"""
        self.assertEqual(self.category.name, 'Test Category')
        self.assertEqual(self.category.slug, 'test-category')
        
    def test_string_representation(self):
        """Test Category string representation"""
        self.assertEqual(str(self.category), 'Test Category')
        
    def test_get_absolute_url(self):
        """Test Category get_absolute_url method"""
        self.assertEqual(
            self.category.get_absolute_url(),
            reverse('category_detail', args=['test-category'])
        )
        
    def test_auto_slug_generation(self):
        """Test slug is automatically generated from name"""
        category = Category.objects.create(name='Auto Slug Test')
        self.assertEqual(category.slug, 'auto-slug-test')
        
class ProductModelTest(TestCase):
    def setUp(self):
        # Create test category
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )
        
        # Create test product
        self.product = Product.objects.create(
            name='Test Product',
            slug='test-product',
            description='This is a test product',
            price=Decimal('99.99'),
            category=self.category,
            stock=10,
            is_active=True
        )
        
    def test_product_creation(self):
        """Test Product model creation"""
        self.assertEqual(self.product.name, 'Test Product')
        self.assertEqual(self.product.slug, 'test-product')
        self.assertEqual(self.product.description, 'This is a test product')
        self.assertEqual(self.product.price, Decimal('99.99'))
        self.assertEqual(self.product.category, self.category)
        self.assertEqual(self.product.stock, 10)
        self.assertTrue(self.product.is_active)
        
    def test_string_representation(self):
        """Test Product string representation"""
        self.assertEqual(str(self.product), 'Test Product')
        
    def test_get_absolute_url(self):
        """Test Product get_absolute_url method"""
        self.assertEqual(
            self.product.get_absolute_url(),
            reverse('product_detail', kwargs={'slug': 'test-product'})
        )
        
    def test_auto_slug_generation(self):
        """Test slug is automatically generated from name"""
        product = Product.objects.create(
            name='Auto Slug Test',
            description='Testing auto slug',
            price=Decimal('19.99'),
            category=self.category
        )
        self.assertEqual(product.slug, 'auto-slug-test')

class CartModelTest(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword'
        )
        
        # Create test category and product
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )
        
        self.product1 = Product.objects.create(
            name='Test Product 1',
            slug='test-product-1',
            description='This is test product 1',
            price=Decimal('10.00'),
            category=self.category,
            stock=10
        )
        
        self.product2 = Product.objects.create(
            name='Test Product 2',
            slug='test-product-2',
            description='This is test product 2',
            price=Decimal('20.00'),
            category=self.category,
            stock=5
        )
        
        # Create cart and cart items
        self.cart = Cart.objects.create(user=self.user)
        self.cart_item1 = CartItem.objects.create(
            cart=self.cart,
            product=self.product1,
            quantity=2
        )
        self.cart_item2 = CartItem.objects.create(
            cart=self.cart,
            product=self.product2,
            quantity=1
        )
        
    def test_cart_creation(self):
        """Test Cart model creation"""
        self.assertEqual(self.cart.user, self.user)
        self.assertIsNotNone(self.cart.created_at)
        
    def test_string_representation(self):
        """Test Cart string representation"""
        self.assertEqual(str(self.cart), f"Cart {self.cart.id}")
        
    def test_total_price_property(self):
        """Test Cart total_price property"""
        # 2 items of $10 + 1 item of $20 = $40
        self.assertEqual(self.cart.total_price, Decimal('40.00'))
        
    def test_total_items_property(self):
        """Test Cart total_items property"""
        # 2 items of product1 + 1 item of product2 = 3 items
        self.assertEqual(self.cart.total_items, 3)
        
    def test_cart_item_string_representation(self):
        """Test CartItem string representation"""
        self.assertEqual(str(self.cart_item1), "2 x Test Product 1")
        
    def test_cart_item_total_price_property(self):
        """Test CartItem total_price property"""
        self.assertEqual(self.cart_item1.total_price, Decimal('20.00'))  # 2 x $10
        self.assertEqual(self.cart_item2.total_price, Decimal('20.00'))  # 1 x $20 