from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Comment, ShippingAddress, CreditCard, ProductRating
import datetime

class CommentForm(forms.ModelForm):
    text = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        label='Your Comment'
    )
    
    class Meta:
        model = Comment
        fields = ['text']

class ProductRatingForm(forms.ModelForm):
    RATING_CHOICES = [(i, i) for i in range(1, 6)]
    
    rating = forms.ChoiceField(
        choices=RATING_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'rating-input'}),
        label='Rate this product'
    )
    
    feedback = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Share your experience with this product'}),
        label='Your Review'
    )
    
    class Meta:
        model = ProductRating
        fields = ['rating', 'feedback']

class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        max_length=254,
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'password1': forms.PasswordInput(attrs={'class': 'form-control'}),
            'password2': forms.PasswordInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to form fields
        for field_name in self.fields:
            self.fields[field_name].widget.attrs['class'] = 'form-control'
            
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with that email already exists. Please use a different email or try to log in.")
        return email

class ShippingAddressForm(forms.ModelForm):
    phone_number = forms.CharField(max_length=20, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    
    class Meta:
        model = ShippingAddress
        fields = ['name', 'phone_number', 'address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'address_line1': forms.TextInput(attrs={'class': 'form-control'}),
            'address_line2': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
        }

class CreditCardForm(forms.ModelForm):
    card_number = forms.CharField(
        max_length=19,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1234 5678 9012 3456'})
    )
    card_holder = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'John Doe'})
    )
    cvv = forms.CharField(
        max_length=4, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '123'})
    )
    expiry_month = forms.ChoiceField(
        choices=[(i, i) for i in range(1, 13)],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    current_year = datetime.datetime.now().year
    expiry_year = forms.ChoiceField(
        choices=[(i, i) for i in range(current_year, current_year + 11)],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    is_default = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = CreditCard
        fields = ['card_number', 'card_holder', 'expiry_month', 'expiry_year', 'is_default']
        
    def clean_card_number(self):
        card_number = self.cleaned_data['card_number'].replace(' ', '')
        if not card_number.isdigit():
            raise forms.ValidationError('Card number must contain only digits')
        if len(card_number) < 13 or len(card_number) > 16:
            raise forms.ValidationError('Card number must be between 13 and 16 digits')
        return card_number
        
    def clean_cvv(self):
        cvv = self.cleaned_data['cvv']
        if not cvv.isdigit():
            raise forms.ValidationError('CVV must contain only digits')
        if len(cvv) < 3 or len(cvv) > 4:
            raise forms.ValidationError('CVV must be 3 or 4 digits')
        return cvv

class PaymentMethodForm(forms.Form):
    PAYMENT_METHODS = [
        ('credit_card', 'Credit Card'),
        ('paypal', 'PayPal'),
        ('bank_transfer', 'Bank Transfer'),
        ('cash_on_delivery', 'Cash on Delivery'),
    ]
    
    payment_method = forms.ChoiceField(
        choices=PAYMENT_METHODS,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    saved_card = forms.ModelChoiceField(
        queryset=CreditCard.objects.none(),
        required=False,
        empty_label="Use a new card",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user and user.is_authenticated:
            self.fields['saved_card'].queryset = CreditCard.objects.filter(user=user)
