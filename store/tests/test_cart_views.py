from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from decimal import Decimal
from store.models import Product, Category, Cart, CartItem

class CartViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword'
        )
        
        # Create test category and product
        self.category = Category.objects.create(name='Test Category', slug='test-category')
        self.product = Product.objects.create(
            name='Test Product',
            slug='test-product',
            description='Test description',
            price=Decimal('10.00'),
            category=self.category,
            stock=10,
            is_active=True
        )
        
        # Create another product for testing multiple items
        self.product2 = Product.objects.create(
            name='Test Product 2',
            slug='test-product-2',
            description='Test description 2',
            price=Decimal('15.00'),
            category=self.category,
            stock=5,
            is_active=True
        )
    
    def test_add_to_cart_authenticated(self):
        """Test adding a product to cart for authenticated user"""
        self.client.login(username='testuser', password='testpassword')
        
        # Add product to cart
        response = self.client.post(
            reverse('add_to_cart', args=[self.product.id]),
            {'quantity': 2}
        )
        
        # Check redirect status
        self.assertEqual(response.status_code, 302)
        
        # Check if cart was created with correct item
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.count(), 1)
        
        cart_item = cart.items.first()
        self.assertEqual(cart_item.product, self.product)
        self.assertEqual(cart_item.quantity, 2)
        
        # Check success message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn('Added Test Product to your cart', str(messages[0]))
    
    def test_add_to_cart_unauthenticated(self):
        """Test adding a product to cart for unauthenticated user"""
        # Add product to cart
        response = self.client.post(
            reverse('add_to_cart', args=[self.product.id]),
            {'quantity': 1}
        )
        
        # Check redirect status
        self.assertEqual(response.status_code, 302)
        
        # Check if cart was created with session_id
        session_id = self.client.session.session_key
        cart = Cart.objects.get(session_id=session_id)
        self.assertEqual(cart.items.count(), 1)
        
        cart_item = cart.items.first()
        self.assertEqual(cart_item.product, self.product)
        self.assertEqual(cart_item.quantity, 1)
    
    def test_add_to_cart_existing_item(self):
        """Test adding a product that already exists in cart"""
        self.client.login(username='testuser', password='testpassword')
        
        # Create cart and add item
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        
        # Add same product again
        response = self.client.post(
            reverse('add_to_cart', args=[self.product.id]),
            {'quantity': 2}
        )
        
        # Check if quantity was updated
        cart_item = CartItem.objects.get(cart=cart, product=self.product)
        self.assertEqual(cart_item.quantity, 3)
        
        # Check info message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn('Updated Test Product quantity in your cart', str(messages[0]))
    
    def test_update_cart(self):
        """Test updating cart item quantity"""
        self.client.login(username='testuser', password='testpassword')
        
        # Create cart and add item
        cart = Cart.objects.create(user=self.user)
        cart_item = CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        
        # Update item quantity
        response = self.client.post(
            reverse('update_cart', args=[cart_item.id]),
            {'quantity': 5}
        )
        
        # Check redirect status
        self.assertEqual(response.status_code, 302)
        
        # Check if quantity was updated
        cart_item.refresh_from_db()
        self.assertEqual(cart_item.quantity, 5)
        
        # Check info message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn('Cart updated successfully', str(messages[0]))
    
    def test_update_cart_zero_quantity(self):
        """Test updating cart item with zero quantity (should remove item)"""
        self.client.login(username='testuser', password='testpassword')
        
        # Create cart and add item
        cart = Cart.objects.create(user=self.user)
        cart_item = CartItem.objects.create(cart=cart, product=self.product, quantity=3)
        
        # Set quantity to 0
        response = self.client.post(
            reverse('update_cart', args=[cart_item.id]),
            {'quantity': 0}
        )
        
        # Check redirect status
        self.assertEqual(response.status_code, 302)
        
        # Check if item was removed
        self.assertEqual(cart.items.count(), 0)
        
        # Check info message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn('Item removed from cart', str(messages[0]))
    
    def test_remove_from_cart(self):
        """Test removing an item from cart"""
        self.client.login(username='testuser', password='testpassword')
        
        # Create cart and add item
        cart = Cart.objects.create(user=self.user)
        cart_item = CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        
        # Remove item
        response = self.client.get(reverse('remove_from_cart', args=[cart_item.id]))
        
        # Check redirect status
        self.assertEqual(response.status_code, 302)
        
        # Check if item was removed
        self.assertEqual(cart.items.count(), 0)
        
        # Check info message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn('Item removed from cart', str(messages[0]))
    
    def test_cart_detail_authenticated(self):
        """Test cart detail view for authenticated user"""
        self.client.login(username='testuser', password='testpassword')
        
        # Create cart and add items
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        CartItem.objects.create(cart=cart, product=self.product2, quantity=1)
        
        # Access cart detail page
        response = self.client.get(reverse('cart_detail'))
        
        # Check status code and template
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'store/cart_detail.html')
        
        # Check context
        self.assertEqual(response.context['cart'], cart)
        self.assertEqual(response.context['cart'].items.count(), 2)
        
        # Check total price calculation
        self.assertEqual(response.context['cart'].total_price, Decimal('35.00'))
    
    def test_cart_detail_unauthenticated(self):
        """Test cart detail view for unauthenticated user"""
        # Access cart detail page
        response = self.client.get(reverse('cart_detail'))
        
        # Check status code and template
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'store/cart_detail.html')
        
        # Check that a new cart was created
        self.assertIsNotNone(response.context['cart'])
        self.assertEqual(response.context['cart'].items.count(), 0)
    
    def test_unauthorized_cart_modification(self):
        """Test unauthorized cart modification"""
        # Create two users
        another_user = User.objects.create_user(
            username='anotheruser',
            email='another@example.com',
            password='anotherpassword'
        )
        
        # Create cart for another user
        another_cart = Cart.objects.create(user=another_user)
        another_cart_item = CartItem.objects.create(cart=another_cart, product=self.product, quantity=1)
        
        # Login as testuser
        self.client.login(username='testuser', password='testpassword')
        
        # Try to update another user's cart
        response = self.client.post(
            reverse('update_cart', args=[another_cart_item.id]),
            {'quantity': 5}
        )
        
        # Check redirect and error message
        self.assertEqual(response.status_code, 302)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("You don't have permission to modify this cart", str(messages[0]))
        
        # Check that cart wasn't modified
        another_cart_item.refresh_from_db()
        self.assertEqual(another_cart_item.quantity, 1)
        
        # Try to remove another user's cart item
        response = self.client.get(reverse('remove_from_cart', args=[another_cart_item.id]))
        
        # Check redirect and error message
        self.assertEqual(response.status_code, 302)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 2)  # Now we have two messages total
        self.assertIn("You don't have permission to modify this cart", str(messages[1]))
        
        # Check that cart item wasn't removed
        self.assertEqual(another_cart.items.count(), 1) 