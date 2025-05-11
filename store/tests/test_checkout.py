from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from decimal import Decimal
from store.models import (
    Product, Category, Cart, CartItem, Order, OrderItem,
    ShippingAddress, CreditCard
)

class CheckoutProcessTest(TestCase):
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
        
        # Create cart with items
        self.cart = Cart.objects.create(user=self.user)
        self.cart_item = CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            quantity=2
        )
        
        # Create shipping address
        self.shipping_address = ShippingAddress.objects.create(
            user=self.user,
            recipient_name='Test User',
            street_address='123 Test St',
            city='Test City',
            state='TS',
            zip_code='12345',
            country='Testland',
            phone_number='1234567890',
            is_default=True
        )
        
        # Create credit card
        self.credit_card = CreditCard.objects.create(
            user=self.user,
            card_number='4111111111111111',
            expiry_month=12,
            expiry_year=2030,
            cvv='123',
            name_on_card='Test User',
            is_default=True
        )
        
        # Create an order for payment testing
        self.order = Order.objects.create(
            user=self.user,
            shipping_address=self.shipping_address,
            total_price=Decimal('20.00'),
            status='pending',
            payment_status=False
        )
        
        # Create order item
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            price=Decimal('10.00')
        )
        
        # Create a processed order for testing cancellation rejection
        self.processed_order = Order.objects.create(
            user=self.user,
            shipping_address=self.shipping_address,
            total_price=Decimal('20.00'),
            status='processing',
            payment_status=True
        )
        
        # Create order item for processed order
        self.processed_order_item = OrderItem.objects.create(
            order=self.processed_order,
            product=self.product,
            quantity=2,
            price=Decimal('10.00')
        )
    
    def test_checkout_unauthenticated(self):
        """Test that checkout redirects to login for unauthenticated users"""
        response = self.client.get(reverse('checkout'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_checkout_authenticated_empty_cart(self):
        """Test checkout with authenticated user but empty cart"""
        self.client.login(username='testuser', password='testpassword')
        
        # Empty the cart
        self.cart_item.delete()
        
        response = self.client.get(reverse('checkout'))
        
        # Should redirect to cart with warning
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('cart_detail'))
        
        # Check for warning message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn('Your cart is empty', str(messages[0]))
    
    def test_checkout_authenticated_with_items(self):
        """Test checkout with authenticated user and items in cart"""
        self.client.login(username='testuser', password='testpassword')
        
        response = self.client.get(reverse('checkout'))
        
        # Should render checkout page
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'store/checkout.html')
        
        # Check context
        self.assertEqual(response.context['cart'], self.cart)
        self.assertEqual(response.context['shipping_addresses'].count(), 1)
        self.assertEqual(response.context['default_address'], self.shipping_address)
        self.assertEqual(response.context['credit_cards'].count(), 1)
    
    def test_payment_unauthenticated(self):
        """Test that payment redirects to login for unauthenticated users"""
        response = self.client.get(reverse('payment', args=[self.order.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_payment_authenticated_get(self):
        """Test payment page loading for authenticated user"""
        self.client.login(username='testuser', password='testpassword')
        
        response = self.client.get(reverse('payment', args=[self.order.id]))
        
        # Should render payment page
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'store/payment.html')
        
        # Check context
        self.assertEqual(response.context['order'], self.order)
    
    def test_payment_authenticated_post(self):
        """Test payment processing for authenticated user"""
        self.client.login(username='testuser', password='testpassword')
        
        response = self.client.post(reverse('payment', args=[self.order.id]))
        
        # Should redirect to order success
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('order_success', args=[self.order.id]))
        
        # Check for success message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn('Payment successful', str(messages[0]))
        
        # Order should be updated
        self.order.refresh_from_db()
        self.assertTrue(self.order.payment_status)
        self.assertEqual(self.order.status, 'processing')
    
    def test_payment_wrong_user(self):
        """Test payment for order by wrong user"""
        # Create another user
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpassword'
        )
        
        # Login as other user
        self.client.login(username='otheruser', password='otherpassword')
        
        # Try to access payment for an order that belongs to testuser
        response = self.client.get(reverse('payment', args=[self.order.id]))
        
        # Should return 404
        self.assertEqual(response.status_code, 404)
    
    def test_order_success(self):
        """Test order success page"""
        self.client.login(username='testuser', password='testpassword')
        
        response = self.client.get(reverse('order_success', args=[self.order.id]))
        
        # Should render order success page
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'store/order_success.html')
        
        # Check context
        self.assertEqual(response.context['order'], self.order)
    
    def test_order_detail(self):
        """Test order detail page"""
        self.client.login(username='testuser', password='testpassword')
        
        response = self.client.get(reverse('order_detail', args=[self.order.id]))
        
        # Should render order detail page
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'store/order_detail.html')
        
        # Check context
        self.assertEqual(response.context['order'], self.order)
    
    def test_order_detail_wrong_user(self):
        """Test order detail for wrong user"""
        # Create another user
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpassword'
        )
        
        # Login as other user
        self.client.login(username='otheruser', password='otherpassword')
        
        # Try to access order detail for an order that belongs to testuser
        response = self.client.get(reverse('order_detail', args=[self.order.id]))
        
        # Should return 404
        self.assertEqual(response.status_code, 404)
    
    def test_cancel_order_pending(self):
        """Test cancelling a pending order"""
        self.client.login(username='testuser', password='testpassword')
        
        response = self.client.post(reverse('cancel_order', args=[self.order.id]))
        
        # Should redirect to profile
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('profile'))
        
        # Check for success message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn('Order cancelled successfully', str(messages[0]))
        
        # Order status should be updated
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'cancelled')
    
    def test_cancel_order_processing(self):
        """Test cancelling a processing order (should be rejected)"""
        self.client.login(username='testuser', password='testpassword')
        
        response = self.client.post(reverse('cancel_order', args=[self.processed_order.id]))
        
        # Should redirect to profile
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('profile'))
        
        # Check for error message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn('This order cannot be cancelled', str(messages[0]))
        
        # Order status should not change
        self.processed_order.refresh_from_db()
        self.assertEqual(self.processed_order.status, 'processing')
    
    def test_cancel_order_wrong_user(self):
        """Test cancelling another user's order"""
        # Create another user
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpassword'
        )
        
        # Login as other user
        self.client.login(username='otheruser', password='otherpassword')
        
        # Try to cancel testuser's order
        response = self.client.post(reverse('cancel_order', args=[self.order.id]))
        
        # Should return 404
        self.assertEqual(response.status_code, 404)
        
        # Order status should not change
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending')
    
    def test_order_bill(self):
        """Test viewing order bill"""
        self.client.login(username='testuser', password='testpassword')
        
        response = self.client.get(reverse('order_bill', args=[self.order.id]))
        
        # Should render bill page
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'store/order_bill.html')
        
        # Check context
        self.assertEqual(response.context['order'], self.order)
    
    def test_order_bill_wrong_user(self):
        """Test viewing bill for another user's order"""
        # Create another user
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpassword'
        )
        
        # Login as other user
        self.client.login(username='otheruser', password='otherpassword')
        
        # Try to view bill for testuser's order
        response = self.client.get(reverse('order_bill', args=[self.order.id]))
        
        # Should return 404
        self.assertEqual(response.status_code, 404)
    
    def test_add_credit_card_get(self):
        """Test add credit card page loading"""
        self.client.login(username='testuser', password='testpassword')
        
        response = self.client.get(reverse('add_credit_card'))
        
        # Should render add credit card page
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'store/add_credit_card.html')
    
    def test_add_credit_card_post(self):
        """Test adding a new credit card"""
        self.client.login(username='testuser', password='testpassword')
        
        # Initial credit card count
        initial_count = CreditCard.objects.count()
        
        # Post data for new credit card
        response = self.client.post(reverse('add_credit_card'), {
            'card_number': '5555555555554444',
            'expiry_month': 10,
            'expiry_year': 2025,
            'cvv': '321',
            'name_on_card': 'New Test User',
            'is_default': False
        })
        
        # Should redirect to profile
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('profile'))
        
        # Check for success message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn('Credit card added successfully', str(messages[0]))
        
        # Credit card count should increase
        self.assertEqual(CreditCard.objects.count(), initial_count + 1)
        
        # New credit card should exist
        self.assertTrue(
            CreditCard.objects.filter(
                card_number='5555555555554444',
                user=self.user
            ).exists()
        ) 