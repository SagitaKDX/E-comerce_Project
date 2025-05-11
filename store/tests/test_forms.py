from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal
import datetime

from store.models import (
    Comment, Product, Category, ShippingAddress,
    CreditCard
)
from store.forms import (
    CommentForm, RegisterForm, ShippingAddressForm,
    CreditCardForm, PaymentMethodForm
)

class CommentFormTest(TestCase):
    def test_comment_form_valid_data(self):
        form = CommentForm(data={
            'text': 'This is a test comment'
        })
        self.assertTrue(form.is_valid())
    
    def test_comment_form_empty_data(self):
        form = CommentForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn('text', form.errors)
        
    def test_comment_form_fields(self):
        """Test that the form has the expected fields"""
        form = CommentForm()
        self.assertEqual(list(form.fields), ['text'])
        
class RegisterFormTest(TestCase):
    def test_register_form_valid_data(self):
        form = RegisterForm(data={
            'username': 'testuser',
            'email': 'test@example.com',
            'password1': 'complexpassword123',
            'password2': 'complexpassword123'
        })
        self.assertTrue(form.is_valid())
    
    def test_register_form_invalid_email(self):
        form = RegisterForm(data={
            'username': 'testuser',
            'email': 'invalid-email',
            'password1': 'complexpassword123',
            'password2': 'complexpassword123'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        
    def test_register_form_passwords_dont_match(self):
        form = RegisterForm(data={
            'username': 'testuser',
            'email': 'test@example.com',
            'password1': 'complexpassword123',
            'password2': 'differentpassword123'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)
        
    def test_register_form_with_existing_username(self):
        # Create a user first
        User.objects.create_user(
            username='existinguser',
            email='existing@example.com',
            password='password123'
        )
        
        # Try to create a new user with the same username
        form = RegisterForm(data={
            'username': 'existinguser',
            'email': 'new@example.com',
            'password1': 'complexpassword123',
            'password2': 'complexpassword123'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
        
class ShippingAddressFormTest(TestCase):
    def test_shipping_address_form_valid_data(self):
        form = ShippingAddressForm(data={
            'name': 'Test User',
            'address_line1': '123 Test St',
            'city': 'Test City',
            'state': 'Test State',
            'postal_code': '12345',
            'country': 'Test Country'
        })
        self.assertTrue(form.is_valid())
    
    def test_shipping_address_form_missing_required_fields(self):
        form = ShippingAddressForm(data={
            'name': 'Test User',
            # Missing address_line1
            'city': 'Test City',
            'state': 'Test State',
            'postal_code': '12345',
            'country': 'Test Country'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('address_line1', form.errors)
        
    def test_shipping_address_form_optional_field(self):
        """Test that address_line2 is optional"""
        form = ShippingAddressForm(data={
            'name': 'Test User',
            'address_line1': '123 Test St',
            # No address_line2
            'city': 'Test City',
            'state': 'Test State',
            'postal_code': '12345',
            'country': 'Test Country'
        })
        self.assertTrue(form.is_valid())
        
class CreditCardFormTest(TestCase):
    def test_credit_card_form_valid_data(self):
        form = CreditCardForm(data={
            'card_number': '4111111111111111',
            'card_holder': 'Test User',
            'expiry_month': 12,
            'expiry_year': datetime.datetime.now().year + 1,
            'cvv': '123',
            'is_default': True
        })
        self.assertTrue(form.is_valid())
    
    def test_credit_card_form_invalid_card_number(self):
        # Test with non-numeric card number
        form = CreditCardForm(data={
            'card_number': 'ABCD1234EFGH5678',
            'card_holder': 'Test User',
            'expiry_month': 12,
            'expiry_year': datetime.datetime.now().year + 1,
            'cvv': '123',
            'is_default': True
        })
        self.assertFalse(form.is_valid())
        self.assertIn('card_number', form.errors)
        
        # Test with card number that's too short
        form = CreditCardForm(data={
            'card_number': '41111',
            'card_holder': 'Test User',
            'expiry_month': 12,
            'expiry_year': datetime.datetime.now().year + 1,
            'cvv': '123',
            'is_default': True
        })
        self.assertFalse(form.is_valid())
        self.assertIn('card_number', form.errors)
        
    def test_credit_card_form_invalid_cvv(self):
        # Test with non-numeric CVV
        form = CreditCardForm(data={
            'card_number': '4111111111111111',
            'card_holder': 'Test User',
            'expiry_month': 12,
            'expiry_year': datetime.datetime.now().year + 1,
            'cvv': 'ABC',
            'is_default': True
        })
        self.assertFalse(form.is_valid())
        self.assertIn('cvv', form.errors)
        
        # Test with CVV that's too short
        form = CreditCardForm(data={
            'card_number': '4111111111111111',
            'card_holder': 'Test User',
            'expiry_month': 12,
            'expiry_year': datetime.datetime.now().year + 1,
            'cvv': '1',
            'is_default': True
        })
        self.assertFalse(form.is_valid())
        self.assertIn('cvv', form.errors)
        
class PaymentMethodFormTest(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword'
        )
        
        # Create credit card for the user
        self.credit_card = CreditCard.objects.create(
            user=self.user,
            card_number='4111111111111111',
            card_holder='Test User',
            expiry_month=12,
            expiry_year=2030,
            is_default=True
        )
        
    def test_payment_method_form_initialization(self):
        """Test form initialization with user"""
        form = PaymentMethodForm(user=self.user)
        
        # Check that saved_card queryset is correctly filtered
        self.assertEqual(form.fields['saved_card'].queryset.count(), 1)
        self.assertEqual(form.fields['saved_card'].queryset[0], self.credit_card)
        
    def test_payment_method_form_valid_data(self):
        form = PaymentMethodForm(
            data={'payment_method': 'credit_card'},
            user=self.user
        )
        self.assertTrue(form.is_valid())
        
    def test_payment_method_form_with_saved_card(self):
        form = PaymentMethodForm(
            data={
                'payment_method': 'credit_card',
                'saved_card': self.credit_card.id
            },
            user=self.user
        )
        self.assertTrue(form.is_valid()) 