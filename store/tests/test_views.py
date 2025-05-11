from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import json

from store.models import (
    Category, Product, Comment, Cart, CartItem,
    UserProfile
)

class HomeViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.home_url = reverse('home')
        
        # Create test category and products
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )
        
        # Create multiple products
        for i in range(10):
            Product.objects.create(
                name=f'Test Product {i}',
                slug=f'test-product-{i}',
                description=f'Description for product {i}',
                price=Decimal(f'{10+i}.99'),
                category=self.category,
                is_active=True
            )
            
    def test_home_view_get(self):
        """Test home view GET request"""
        response = self.client.get(self.home_url)
        
        # Check that response is successful
        self.assertEqual(response.status_code, 200)
        
        # Check that the correct template is used
        self.assertTemplateUsed(response, 'store/home.html')
        
        # Check that products are in context
        self.assertIn('featured_products', response.context)
        
        # Check that only active products are included
        self.assertLessEqual(len(response.context['featured_products']), 8)
        
    def test_home_view_with_refresh_parameter(self):
        """Test home view with refresh parameter"""
        response = self.client.get(f"{self.home_url}?refresh=1")
        
        # Check that response is successful
        self.assertEqual(response.status_code, 200)
        
        # Check for cache control headers
        self.assertEqual(response.get('Cache-Control'), 'no-cache, no-store, must-revalidate')
        self.assertEqual(response.get('Pragma'), 'no-cache')
        self.assertEqual(response.get('Expires'), '0')
        
class ProductListViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.product_list_url = reverse('product_list')
        
        # Create test categories
        self.category1 = Category.objects.create(
            name='Category 1',
            slug='category-1'
        )
        
        self.category2 = Category.objects.create(
            name='Category 2',
            slug='category-2'
        )
        
        # Create products in each category
        for i in range(5):
            Product.objects.create(
                name=f'Product 1-{i}',
                slug=f'product-1-{i}',
                description=f'Description for product 1-{i}',
                price=Decimal(f'{10+i}.99'),
                category=self.category1,
                is_active=True
            )
            
        for i in range(5):
            Product.objects.create(
                name=f'Product 2-{i}',
                slug=f'product-2-{i}',
                description=f'Description for product 2-{i}',
                price=Decimal(f'{20+i}.99'),
                category=self.category2,
                is_active=True
            )
            
        # Create one inactive product
        Product.objects.create(
            name='Inactive Product',
            slug='inactive-product',
            description='This product is inactive',
            price=Decimal('99.99'),
            category=self.category1,
            is_active=False
        )
            
    def test_product_list_view_get(self):
        """Test product list view GET request"""
        response = self.client.get(self.product_list_url)
        
        # Check that response is successful
        self.assertEqual(response.status_code, 200)
        
        # Check that the correct template is used
        self.assertTemplateUsed(response, 'store/product_list.html')
        
        # Check that products are in context
        self.assertIn('products', response.context)
        
        # Check that only active products are included
        self.assertEqual(len(response.context['products']), 10)
        
    def test_product_list_search(self):
        """Test product list search functionality"""
        response = self.client.get(f"{self.product_list_url}?search=Product 1")
        
        # Check that response is successful
        self.assertEqual(response.status_code, 200)
        
        # Check that only products matching the search are included
        self.assertEqual(len(response.context['products']), 5)
        
    def test_product_list_category_filter(self):
        """Test product list category filter"""
        response = self.client.get(f"{self.product_list_url}?category=category-1")
        
        # Check that response is successful
        self.assertEqual(response.status_code, 200)
        
        # Check that only products in the category are included
        self.assertEqual(len(response.context['products']), 5)
        
    def test_product_list_sorting(self):
        """Test product list sorting"""
        # Test price ascending
        response = self.client.get(f"{self.product_list_url}?sort=price_asc")
        self.assertEqual(response.status_code, 200)
        products = list(response.context['products'])
        self.assertLessEqual(products[0].price, products[-1].price)
        
        # Test price descending
        response = self.client.get(f"{self.product_list_url}?sort=price_desc")
        self.assertEqual(response.status_code, 200)
        products = list(response.context['products'])
        self.assertGreaterEqual(products[0].price, products[-1].price)
        
class ProductDetailViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create user
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
        
        self.product = Product.objects.create(
            name='Test Product',
            slug='test-product',
            description='This is a test product',
            price=Decimal('99.99'),
            category=self.category,
            is_active=True
        )
        
        # URL for the product detail
        self.product_detail_url = reverse('product_detail', kwargs={'slug': 'test-product'})
        
        # Add comments to the product
        Comment.objects.create(
            product=self.product,
            user=self.user,
            text='This is a comment',
            status='new'
        )
            
    def test_product_detail_view_get(self):
        """Test product detail view GET request"""
        response = self.client.get(self.product_detail_url)
        
        # Check that response is successful
        self.assertEqual(response.status_code, 200)
        
        # Check that the correct template is used
        self.assertTemplateUsed(response, 'store/product_detail.html')
        
        # Check that product is in context
        self.assertIn('product', response.context)
        self.assertEqual(response.context['product'], self.product)
        
        # Check that comments are in context
        self.assertIn('comments', response.context)
        self.assertEqual(len(response.context['comments']), 1)
        
        # Check that comment form is in context
        self.assertIn('comment_form', response.context)
        
    def test_product_detail_view_inactive_product(self):
        """Test product detail view with inactive product"""
        # Create inactive product
        inactive_product = Product.objects.create(
            name='Inactive Product',
            slug='inactive-product',
            description='This product is inactive',
            price=Decimal('99.99'),
            category=self.category,
            is_active=False
        )
        
        # Try to access the inactive product
        url = reverse('product_detail', kwargs={'slug': 'inactive-product'})
        response = self.client.get(url)
        
        # Check that we get a 404 response
        self.assertEqual(response.status_code, 404)
        
class AddCommentViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create user
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
        
        self.product = Product.objects.create(
            name='Test Product',
            slug='test-product',
            description='This is a test product',
            price=Decimal('99.99'),
            category=self.category,
            is_active=True
        )
        
        # URL for adding a comment
        self.add_comment_url = reverse('add_comment', kwargs={'product_id': self.product.id})
            
    def test_add_comment_authenticated(self):
        """Test adding a comment when authenticated"""
        # Login
        self.client.login(username='testuser', password='testpassword')
        
        # Post a comment
        response = self.client.post(self.add_comment_url, {
            'text': 'This is a test comment'
        })
        
        # Check that we are redirected to the product detail page
        self.assertRedirects(
            response, 
            reverse('product_detail', kwargs={'slug': 'test-product'})
        )
        
        # Check that the comment was created
        self.assertEqual(Comment.objects.count(), 1)
        comment = Comment.objects.first()
        self.assertEqual(comment.text, 'This is a test comment')
        self.assertEqual(comment.user, self.user)
        self.assertEqual(comment.product, self.product)
        
    def test_add_comment_unauthenticated(self):
        """Test adding a comment when not authenticated"""
        # Post a comment without logging in
        response = self.client.post(self.add_comment_url, {
            'text': 'This is a test comment'
        })
        
        # Check that we are redirected to login page
        self.assertRedirects(
            response, 
            f"{reverse('login')}?next={self.add_comment_url}"
        )
        
        # Check that no comment was created
        self.assertEqual(Comment.objects.count(), 0) 