import time
import unittest
from decimal import Decimal

from django.test import TransactionTestCase, Client, RequestFactory
from django.urls import reverse
from django.contrib.auth.models import User
from django.db import connection, reset_queries, transaction
from django.test.utils import CaptureQueriesContext
from django.conf import settings

from store.models import (
    Category, Product, Cart, CartItem,
    Order, OrderItem, ShippingAddress, UserProfile
)

class BasePerformanceTest(TransactionTestCase):
    reset_sequences = True
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Only instantiate the test client and request factory here
        cls.factory = RequestFactory()
        cls.client = Client()
    
    def setUp(self):
        # Create test data within transaction for each test
        self._create_test_data()
        
        # Login user for authenticated tests
        self.client.login(username='performancetest', password='testpassword123')
        
        # Create cart for user
        self.cart = Cart.objects.create(user=self.user)
        
        # Reset queries before each test
        reset_queries()
    
    def _create_test_data(self):
        """Create test data that each test needs"""
        with transaction.atomic():
            # Clean up any existing test data
            self._cleanup_test_data()
            
            # Create test user
            self.user = User.objects.create_user(
                username='performancetest',
                email='performance@example.com',
                password='testpassword123'
            )
            
            # Create user profile
            self.profile = UserProfile.objects.create(
                user=self.user,
                role='customer',
                is_email_verified=True
            )
            
            # Create categories
            print("Creating test categories...")
            self.categories = []
            for i in range(5):
                category = Category.objects.create(
                    name=f'Category {i}',
                    slug=f'category-{i}'
                )
                self.categories.append(category)
            
            # Create products - reduce to smaller set for faster testing
            print("Creating test products...")
            self.products = []
            for i in range(50):  # Reduced from 100 to 50
                category_index = i % 5
                product = Product.objects.create(
                    name=f'Product {i}',
                    slug=f'product-{i}',
                    description=f'This is product {i} for performance testing',
                    price=Decimal(f'{(i % 10) * 10 + 9}.99'),
                    category=self.categories[category_index],
                    stock=100,
                    is_active=True
                )
                self.products.append(product)
            
            # Create shipping address
            self.shipping_address = ShippingAddress.objects.create(
                user=self.user,
                name='Performance Test',
                address_line1='123 Performance St',
                city='Test City',
                state='Test State',
                postal_code='12345',
                country='Test Country',
                is_default=True
            )
    
    def _cleanup_test_data(self):
        """Clean up test data to prevent conflicts"""
        # Use more specific queries to delete only our test data
        OrderItem.objects.filter(order__user__username='performancetest').delete()
        Order.objects.filter(user__username='performancetest').delete()
        CartItem.objects.filter(cart__user__username='performancetest').delete()
        Cart.objects.filter(user__username='performancetest').delete()
        ShippingAddress.objects.filter(user__username='performancetest').delete()
        Product.objects.filter(name__startswith='Product ').delete()
        Category.objects.filter(name__startswith='Category ').delete()
        UserProfile.objects.filter(user__username='performancetest').delete()
        User.objects.filter(username='performancetest').delete()
            
    def tearDown(self):
        # Clean up after each test
        self._cleanup_test_data()

class ProductListingPerformanceTest(BasePerformanceTest):
    def test_home_page_load_time(self):
        url = reverse('home')
        
        start_time = time.time()
        with CaptureQueriesContext(connection) as context:
            response = self.client.get(url)
        end_time = time.time()
        
        self.assertEqual(response.status_code, 200)
        
        execution_time = end_time - start_time
        query_count = len(context.captured_queries)
        
        print(f"Home page load time: {execution_time:.4f} seconds")
        print(f"Number of queries: {query_count}")
        
        # Assert reasonable performance
        self.assertLess(execution_time, 1.0, "Home page load took too long")
        self.assertLess(query_count, 20, "Home page used too many queries")
    
    def test_product_list_performance(self):
        url = reverse('product_list')
        
        start_time = time.time()
        with CaptureQueriesContext(connection) as context:
            response = self.client.get(url)
        end_time = time.time()
        
        self.assertEqual(response.status_code, 200)
        
        execution_time = end_time - start_time
        query_count = len(context.captured_queries)
        
        print(f"Product list load time: {execution_time:.4f} seconds")
        print(f"Number of queries: {query_count}")
        
        # Assert reasonable performance
        self.assertLess(execution_time, 1.0, "Product list load took too long")
        self.assertLess(query_count, 20, "Product list used too many queries")
    
    def test_category_filter_performance(self):
        url = reverse('product_list') + f"?category={self.categories[0].slug}"
        
        start_time = time.time()
        with CaptureQueriesContext(connection) as context:
            response = self.client.get(url)
        end_time = time.time()
        
        self.assertEqual(response.status_code, 200)
        
        execution_time = end_time - start_time
        query_count = len(context.captured_queries)
        
        print(f"Category filter load time: {execution_time:.4f} seconds")
        print(f"Number of queries: {query_count}")
        
        # Assert reasonable performance
        self.assertLess(execution_time, 1.0, "Category filter load took too long")
        self.assertLess(query_count, 20, "Category filter used too many queries")
    
    def test_search_performance(self):
        url = reverse('product_list') + "?search=Product"
        
        start_time = time.time()
        with CaptureQueriesContext(connection) as context:
            response = self.client.get(url)
        end_time = time.time()
        
        self.assertEqual(response.status_code, 200)
        
        execution_time = end_time - start_time
        query_count = len(context.captured_queries)
        
        print(f"Search results load time: {execution_time:.4f} seconds")
        print(f"Number of queries: {query_count}")
        
        # Assert reasonable performance
        self.assertLess(execution_time, 1.0, "Search results load took too long")
        self.assertLess(query_count, 20, "Search used too many queries")

class ProductDetailPerformanceTest(BasePerformanceTest):
    def test_product_detail_performance(self):
        url = reverse('product_detail', kwargs={'slug': self.products[0].slug})
        
        start_time = time.time()
        with CaptureQueriesContext(connection) as context:
            response = self.client.get(url)
        end_time = time.time()
        
        self.assertEqual(response.status_code, 200)
        
        execution_time = end_time - start_time
        query_count = len(context.captured_queries)
        
        print(f"Product detail load time: {execution_time:.4f} seconds")
        print(f"Number of queries: {query_count}")
        
        # Assert reasonable performance
        self.assertLess(execution_time, 1.0, "Product detail load took too long")
        self.assertLess(query_count, 15, "Product detail used too many queries")

class CartPerformanceTest(BasePerformanceTest):
    def test_add_to_cart_performance(self):
        url = reverse('add_to_cart')
        data = {
            'product_id': self.products[0].id,
            'quantity': 1
        }
        
        start_time = time.time()
        with CaptureQueriesContext(connection) as context:
            response = self.client.post(url, data)
        end_time = time.time()
        
        execution_time = end_time - start_time
        query_count = len(context.captured_queries)
        
        print(f"Add to cart operation time: {execution_time:.4f} seconds")
        print(f"Number of queries: {query_count}")
        
        # Assert reasonable performance
        self.assertLess(execution_time, 0.5, "Add to cart took too long")
        self.assertLess(query_count, 10, "Add to cart used too many queries")
    
    def test_view_cart_performance(self):
        # Add some items to cart first
        for i in range(5):
            CartItem.objects.create(
                cart=self.cart,
                product=self.products[i],
                quantity=1
            )
        
        url = reverse('cart')
        
        start_time = time.time()
        with CaptureQueriesContext(connection) as context:
            response = self.client.get(url)
        end_time = time.time()
        
        self.assertEqual(response.status_code, 200)
        
        execution_time = end_time - start_time
        query_count = len(context.captured_queries)
        
        print(f"View cart load time: {execution_time:.4f} seconds")
        print(f"Number of queries: {query_count}")
        
        # Assert reasonable performance
        self.assertLess(execution_time, 0.5, "View cart load took too long")
        self.assertLess(query_count, 15, "View cart used too many queries")

class CheckoutPerformanceTest(BasePerformanceTest):
    def test_checkout_page_performance(self):
        # Add items to cart first
        for i in range(3):
            CartItem.objects.create(
                cart=self.cart,
                product=self.products[i],
                quantity=1
            )
            
        url = reverse('checkout')
        
        start_time = time.time()
        with CaptureQueriesContext(connection) as context:
            response = self.client.get(url)
        end_time = time.time()
        
        self.assertEqual(response.status_code, 200)
        
        execution_time = end_time - start_time
        query_count = len(context.captured_queries)
        
        print(f"Checkout page load time: {execution_time:.4f} seconds")
        print(f"Number of queries: {query_count}")
        
        # Assert reasonable performance
        self.assertLess(execution_time, 1.0, "Checkout page load took too long")
        self.assertLess(query_count, 20, "Checkout page used too many queries")

class BulkOperationsPerformanceTest(BasePerformanceTest):
    def test_bulk_product_creation_performance(self):
        num_products = 100
        start_category = self.categories[0]
        
        products_to_create = [
            Product(
                name=f'Bulk Product {i}',
                slug=f'bulk-product-{i}',
                description=f'Bulk created product {i}',
                price=Decimal('19.99'),
                category=start_category,
                stock=100,
                is_active=True
            )
            for i in range(num_products)
        ]
        
        start_time = time.time()
        Product.objects.bulk_create(products_to_create)
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        print(f"Bulk creation of {num_products} products: {execution_time:.4f} seconds")
        
        # Assert reasonable performance
        self.assertLess(execution_time, 2.0, "Bulk product creation took too long")

if __name__ == '__main__':
    unittest.main() 