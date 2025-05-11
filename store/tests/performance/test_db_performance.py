import time
from decimal import Decimal

from django.test import TransactionTestCase
from django.contrib.auth.models import User
from django.db import connection, reset_queries, transaction
from django.db.models import Q, Count, Prefetch, F

from store.models import (
    Category, Product, Cart, CartItem, Order, OrderItem,
    UserProfile, ShippingAddress, Comment
)

class DatabaseQueryPerformanceTest(TransactionTestCase):
    reset_sequences = True
    
    def setUp(self):
        # Create test data within transaction
        with transaction.atomic():
            # Clean up any existing test data first
            self._cleanup_test_data()
            
            # Create users
            print("Creating test users...")
            self.users = []
            for i in range(5):  # Reduced from 10 to 5
                user = User.objects.create_user(
                    username=f'dbtest{i}',
                    email=f'dbtest{i}@example.com',
                    password='testpassword123'
                )
                self.users.append(user)
                
                # Create profile
                UserProfile.objects.create(
                    user=user,
                    role='customer',
                    is_email_verified=True
                )
            
            # Create categories
            print("Creating test categories...")
            self.categories = []
            for i in range(5):
                category = Category.objects.create(
                    name=f'DB Category {i}',
                    slug=f'db-category-{i}'
                )
                self.categories.append(category)
            
            # Create products (reduced dataset)
            print("Creating test products...")
            self.products = []
            for i in range(100):  # Reduced from 500 to 100
                category_index = i % 5
                product = Product.objects.create(
                    name=f'DB Product {i}',
                    slug=f'db-product-{i}',
                    description=f'This is product {i} for database performance testing',
                    price=Decimal(f'{(i % 10) * 10 + 9}.99'),
                    category=self.categories[category_index],
                    stock=100,
                    is_active=True
                )
                self.products.append(product)
            
            # Create comments (reduced)
            print("Creating test comments...")
            for i in range(200):  # Reduced from 1000 to 200
                product_index = i % 100  # Now using 100 products
                user_index = i % 5  # Now using 5 users
                Comment.objects.create(
                    product=self.products[product_index],
                    user=self.users[user_index],
                    text=f'This is comment {i} for database testing',
                    rating=i % 5 + 1
                )
            
            # Create carts and cart items
            print("Creating test carts...")
            self.carts = []
            for i in range(5):  # Reduced from 10 to 5
                cart = Cart.objects.create(user=self.users[i])
                self.carts.append(cart)
                
                # Add items to cart
                for j in range(3):  # Reduced from 5 to 3
                    product_index = (i * 3 + j) % 100
                    CartItem.objects.create(
                        cart=cart,
                        product=self.products[product_index],
                        quantity=j + 1
                    )
            
            # Create shipping addresses
            print("Creating test shipping addresses...")
            self.addresses = []
            for i in range(5):  # Reduced from 10 to 5
                address = ShippingAddress.objects.create(
                    user=self.users[i],
                    name=f'DB Test User {i}',
                    address_line1=f'{i} DB Test St',
                    city='Test City',
                    state='Test State',
                    postal_code='12345',
                    country='Test Country',
                    is_default=True
                )
                self.addresses.append(address)
            
            # Create orders
            print("Creating test orders...")
            self.orders = []
            for i in range(20):  # Reduced from 50 to 20
                user_index = i % 5
                order = Order.objects.create(
                    user=self.users[user_index],
                    shipping_address=self.addresses[user_index],
                    status='processing' if i % 3 == 0 else 'pending',
                    payment_status=i % 2 == 0,
                    order_number=f'DB-ORD-{i}'
                )
                self.orders.append(order)
                
                # Create order items
                for j in range(2):  # Reduced from 3 to 2
                    product_index = (i * 2 + j) % 100
                    OrderItem.objects.create(
                        order=order,
                        product=self.products[product_index],
                        quantity=j + 1,
                        price=self.products[product_index].price
                    )
        
        # Reset queries before tests run
        reset_queries()
    
    def _cleanup_test_data(self):
        """Clean up test data to prevent conflicts"""
        # Use more specific queries to delete only performance test data
        OrderItem.objects.filter(order__order_number__startswith='DB-ORD-').delete()
        Order.objects.filter(order_number__startswith='DB-ORD-').delete()
        CartItem.objects.filter(cart__user__username__startswith='dbtest').delete()
        Cart.objects.filter(user__username__startswith='dbtest').delete()
        Comment.objects.filter(product__name__startswith='DB Product').delete()
        Product.objects.filter(name__startswith='DB Product').delete()
        Category.objects.filter(name__startswith='DB Category').delete()
        ShippingAddress.objects.filter(user__username__startswith='dbtest').delete()
        UserProfile.objects.filter(user__username__startswith='dbtest').delete()
        User.objects.filter(username__startswith='dbtest').delete()
        # Also clean up any created products from bulk tests
        Product.objects.filter(name__startswith='Individual Create').delete()
        Product.objects.filter(name__startswith='Bulk Create').delete()
    
    def tearDown(self):
        # Clean up after each test
        self._cleanup_test_data()

    def test_basic_query_performance(self):
        print("\nTesting basic queries...")
        
        # Test simple filter
        start_time = time.time()
        products = list(Product.objects.filter(price__gt=50))
        query_count = len(connection.queries)
        print(f"Simple filter query took {time.time() - start_time:.4f} seconds, {query_count} queries, returned {len(products)} products")
        self.assertLess(query_count, 2, "Simple filter should execute in at most 1 query")
        
        reset_queries()
        
        # Test complex filter
        start_time = time.time()
        products = list(Product.objects.filter(
            Q(price__gt=50) & Q(category__name__contains='DB') & Q(stock__gte=10)
        ))
        query_count = len(connection.queries)
        print(f"Complex filter query took {time.time() - start_time:.4f} seconds, {query_count} queries, returned {len(products)} products")
        self.assertLess(query_count, 2, "Complex filter should execute in at most 1 query")
    
    def test_foreign_key_query_performance(self):
        print("\nTesting foreign key queries...")
        
        # Test foreign key query without select_related
        reset_queries()
        start_time = time.time()
        products = list(Product.objects.filter(category__name__contains='DB'))
        for product in products[:10]:  # Access category for first 10 products
            category_name = product.category.name
        query_count = len(connection.queries)
        print(f"FK query without select_related took {time.time() - start_time:.4f} seconds, {query_count} queries")
        
        # Test foreign key query with select_related
        reset_queries()
        start_time = time.time()
        products = list(Product.objects.select_related('category').filter(category__name__contains='DB'))
        for product in products[:10]:  # Access category for first 10 products
            category_name = product.category.name
        query_count = len(connection.queries)
        print(f"FK query with select_related took {time.time() - start_time:.4f} seconds, {query_count} queries")
        
        self.assertLess(query_count, 2, "FK query with select_related should execute in at most 1 query")
    
    def test_reverse_relation_query_performance(self):
        print("\nTesting reverse relation queries...")
        
        # Test reverse relation without prefetch_related
        reset_queries()
        start_time = time.time()
        categories = list(Category.objects.all())
        product_count = 0
        for category in categories:
            products = list(category.product_set.all())
            product_count += len(products)
        query_count = len(connection.queries)
        print(f"Reverse relation without prefetch_related took {time.time() - start_time:.4f} seconds, {query_count} queries")
        
        # Test reverse relation with prefetch_related
        reset_queries()
        start_time = time.time()
        categories = list(Category.objects.prefetch_related('product_set'))
        product_count = 0
        for category in categories:
            products = list(category.product_set.all())
            product_count += len(products)
        query_count = len(connection.queries)
        print(f"Reverse relation with prefetch_related took {time.time() - start_time:.4f} seconds, {query_count} queries")
        
        self.assertLess(query_count, 10, "Reverse relation with prefetch_related should execute in a reasonable number of queries")
    
    def test_annotation_and_aggregation_performance(self):
        print("\nTesting annotation and aggregation queries...")
        
        # Test aggregation
        reset_queries()
        start_time = time.time()
        categories = list(Category.objects.annotate(product_count=Count('product')))
        query_count = len(connection.queries)
        print(f"Annotation query took {time.time() - start_time:.4f} seconds, {query_count} queries")
        self.assertLess(query_count, 2, "Annotation query should execute in at most 1 query")
        
        # Test complex aggregation
        reset_queries()
        start_time = time.time()
        products_with_comments = list(Product.objects.annotate(
            comment_count=Count('comment'),
            avg_rating=F('comment_count')
        ).filter(comment_count__gt=0).order_by('-comment_count'))
        query_count = len(connection.queries)
        print(f"Complex annotation query took {time.time() - start_time:.4f} seconds, {query_count} queries, returned {len(products_with_comments)} products")
        self.assertLess(query_count, 2, "Complex annotation query should execute in at most 1 query")
    
    def test_bulk_create_performance(self):
        print("\nTesting bulk create performance...")
        
        # Test individual creates
        reset_queries()
        start_time = time.time()
        for i in range(100):
            Product.objects.create(
                name=f'Individual Create {i}',
                slug=f'individual-create-{i}',
                description=f'Product created individually {i}',
                price=Decimal('9.99'),
                category=self.categories[0],
                stock=10,
                is_active=True
            )
        query_count = len(connection.queries)
        individual_time = time.time() - start_time
        print(f"100 individual creates took {individual_time:.4f} seconds, {query_count} queries")
        
        # Test bulk create
        reset_queries()
        start_time = time.time()
        products_to_create = [
            Product(
                name=f'Bulk Create {i}',
                slug=f'bulk-create-{i}',
                description=f'Product created in bulk {i}',
                price=Decimal('9.99'),
                category=self.categories[0],
                stock=10,
                is_active=True
            )
            for i in range(100)
        ]
        Product.objects.bulk_create(products_to_create)
        query_count = len(connection.queries)
        bulk_time = time.time() - start_time
        print(f"Bulk create of 100 products took {bulk_time:.4f} seconds, {query_count} queries")
        
        # Clean up created products
        Product.objects.filter(name__startswith='Individual Create').delete()
        Product.objects.filter(name__startswith='Bulk Create').delete()
        
        self.assertLess(bulk_time, individual_time, "Bulk create should be faster than individual creates")
        self.assertLess(query_count, 10, "Bulk create should use fewer queries than individual creates") 