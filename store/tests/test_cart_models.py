from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal
from store.models import Cart, CartItem, Product, Category

class CartModelTest(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword'
        )
        
        # Create test category
        self.category = Category.objects.create(name='Test Category', slug='test-category')
        
        # Create test products
        self.product1 = Product.objects.create(
            name='Test Product 1',
            slug='test-product-1',
            description='Test description 1',
            price=Decimal('10.00'),
            category=self.category,
            stock=10,
            is_active=True
        )
        
        self.product2 = Product.objects.create(
            name='Test Product 2',
            slug='test-product-2',
            description='Test description 2',
            price=Decimal('15.00'),
            category=self.category,
            stock=5,
            is_active=True
        )
        
        # Create cart
        self.cart = Cart.objects.create(user=self.user)
        
        # Add items to cart
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
        """Test cart creation"""
        self.assertEqual(Cart.objects.count(), 1)
        self.assertEqual(self.cart.user, self.user)
        self.assertIsNone(self.cart.session_id)
    
    def test_cart_session_creation(self):
        """Test cart creation with session_id"""
        session_cart = Cart.objects.create(session_id='test_session_id')
        self.assertEqual(Cart.objects.count(), 2)
        self.assertIsNone(session_cart.user)
        self.assertEqual(session_cart.session_id, 'test_session_id')
    
    def test_cart_string_representation(self):
        """Test cart string representation"""
        self.assertEqual(str(self.cart), f"Cart {self.cart.id}")
    
    def test_cart_total_price(self):
        """Test cart total_price property"""
        # 2 x $10.00 + 1 x $15.00 = $35.00
        self.assertEqual(self.cart.total_price, Decimal('35.00'))
        
        # Add one more of product2
        self.cart_item2.quantity = 2
        self.cart_item2.save()
        
        # 2 x $10.00 + 2 x $15.00 = $50.00
        self.assertEqual(self.cart.total_price, Decimal('50.00'))
    
    def test_cart_total_items(self):
        """Test cart total_items property"""
        # 2 + 1 = 3 items
        self.assertEqual(self.cart.total_items, 3)
        
        # Add more items
        self.cart_item1.quantity = 4
        self.cart_item1.save()
        
        # 4 + 1 = 5 items
        self.assertEqual(self.cart.total_items, 5)
    
    def test_cart_with_no_items(self):
        """Test cart with no items"""
        empty_cart = Cart.objects.create(session_id='empty_session')
        self.assertEqual(empty_cart.total_price, Decimal('0'))
        self.assertEqual(empty_cart.total_items, 0)
    
    def test_cart_item_creation(self):
        """Test cart item creation"""
        self.assertEqual(CartItem.objects.count(), 2)
        self.assertEqual(self.cart_item1.cart, self.cart)
        self.assertEqual(self.cart_item1.product, self.product1)
        self.assertEqual(self.cart_item1.quantity, 2)
    
    def test_cart_item_string_representation(self):
        """Test cart item string representation"""
        self.assertEqual(str(self.cart_item1), "2 x Test Product 1")
    
    def test_cart_item_total_price(self):
        """Test cart item total_price property"""
        # 2 x $10.00 = $20.00
        self.assertEqual(self.cart_item1.total_price, Decimal('20.00'))
        
        # Change quantity to 3
        self.cart_item1.quantity = 3
        self.cart_item1.save()
        
        # 3 x $10.00 = $30.00
        self.assertEqual(self.cart_item1.total_price, Decimal('30.00'))
    
    def test_cart_items_unique_constraint(self):
        """Test unique_together constraint for cart and product"""
        # Attempting to add the same product to the cart again should raise an error
        with self.assertRaises(Exception):
            CartItem.objects.create(
                cart=self.cart,
                product=self.product1,
                quantity=1
            )
    
    def test_cart_delete_cascade(self):
        """Test that cart items are deleted when cart is deleted"""
        self.assertEqual(CartItem.objects.count(), 2)
        self.cart.delete()
        self.assertEqual(CartItem.objects.count(), 0)
    
    def test_cart_item_update_methods(self):
        """Test updating cart item quantity"""
        # Initial quantity is 2
        self.assertEqual(self.cart_item1.quantity, 2)
        
        # Update quantity
        self.cart_item1.quantity = 4
        self.cart_item1.save()
        
        # Refresh from database
        self.cart_item1.refresh_from_db()
        self.assertEqual(self.cart_item1.quantity, 4)
        
        # Total price should update
        self.assertEqual(self.cart_item1.total_price, Decimal('40.00')) 