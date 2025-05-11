from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from io import BytesIO
from PIL import Image
import tempfile
import os

from store.models import (
    Category, Product, Order, OrderItem,
    ShippingAddress, CreditCard
)

class OrderModelTest(TestCase):
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
        
        # Create shipping address
        self.shipping_address = ShippingAddress.objects.create(
            user=self.user,
            name='Test User',
            address_line1='123 Test St',
            city='Test City',
            state='Test State',
            postal_code='12345',
            country='Test Country',
            is_default=True
        )
        
        # Create order and order items
        self.order = Order.objects.create(
            user=self.user,
            shipping_address=self.shipping_address,
            status='pending',
            payment_status=False,
            payment_method='Credit Card',
            order_number='ORD12345'
        )
        
        self.order_item1 = OrderItem.objects.create(
            order=self.order,
            product=self.product1,
            price=self.product1.price,
            quantity=2
        )
        
        self.order_item2 = OrderItem.objects.create(
            order=self.order,
            product=self.product2,
            price=self.product2.price,
            quantity=1
        )
        
    def test_order_creation(self):
        """Test Order model creation"""
        self.assertEqual(self.order.user, self.user)
        self.assertEqual(self.order.shipping_address, self.shipping_address)
        self.assertEqual(self.order.status, 'pending')
        self.assertFalse(self.order.payment_status)
        self.assertEqual(self.order.payment_method, 'Credit Card')
        self.assertEqual(self.order.order_number, 'ORD12345')
        
    def test_string_representation(self):
        """Test Order string representation"""
        self.assertEqual(str(self.order), f'Order {self.order.order_number}')
        
    def test_total_price_property(self):
        """Test Order total_price property"""
        # 2 items of $10 + 1 item of $20 = $40
        self.assertEqual(self.order.total_price, Decimal('40.00'))
        
    def test_order_item_string_representation(self):
        """Test OrderItem string representation"""
        self.assertEqual(
            str(self.order_item1), 
            f"2 x Test Product 1 in Order {self.order.order_number}"
        )
        
    def test_order_item_total_price_property(self):
        """Test OrderItem total_price property"""
        self.assertEqual(self.order_item1.total_price, Decimal('20.00'))  # 2 x $10
        self.assertEqual(self.order_item2.total_price, Decimal('20.00'))  # 1 x $20
        
    def test_order_number_generation(self):
        """Test order number is generated if not provided"""
        order = Order.objects.create(
            user=self.user,
            shipping_address=self.shipping_address,
            status='pending'
        )
        # Save first to trigger save method
        order.save()
        
        # Check that an order number was generated
        self.assertIsNotNone(order.order_number)
        self.assertTrue(order.order_number.startswith('ORD'))

class CreditCardModelTest(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword'
        )
        
        # Create credit card
        self.credit_card = CreditCard.objects.create(
            user=self.user,
            card_number='4111111111111111',
            card_holder='Test User',
            expiry_month=12,
            expiry_year=2030,
            cvv='123',  # This should be cleared by the save method
            is_default=True
        )
        
    def test_credit_card_creation(self):
        """Test CreditCard model creation"""
        self.assertEqual(self.credit_card.user, self.user)
        self.assertEqual(self.credit_card.card_number, '4111111111111111')
        self.assertEqual(self.credit_card.card_holder, 'Test User')
        self.assertEqual(self.credit_card.expiry_month, 12)
        self.assertEqual(self.credit_card.expiry_year, 2030)
        self.assertIsNone(self.credit_card.cvv)  # Should be None after save
        self.assertTrue(self.credit_card.is_default)
        
    def test_string_representation(self):
        """Test CreditCard string representation"""
        self.assertEqual(
            str(self.credit_card), 
            f"**** **** **** 1111 - Test User"
        )
        
    def test_masked_number_property(self):
        """Test CreditCard masked_number property"""
        self.assertEqual(self.credit_card.masked_number, "**** **** **** 1111")
        
    def test_expiry_date_property(self):
        """Test CreditCard expiry_date property"""
        self.assertEqual(self.credit_card.expiry_date, "12/30")
        
    def test_default_card_handling(self):
        """Test that setting a card as default removes default status from other cards"""
        # Create a second card
        card2 = CreditCard.objects.create(
            user=self.user,
            card_number='5555555555554444',
            card_holder='Test User',
            expiry_month=10,
            expiry_year=2025,
            is_default=True
        )
        
        # Refresh the first card from the database
        self.credit_card.refresh_from_db()
        
        # Check that the first card is no longer the default
        self.assertFalse(self.credit_card.is_default)
        self.assertTrue(card2.is_default) 