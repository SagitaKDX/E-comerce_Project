from django import forms
from store.models import Voucher
from django.utils import timezone

class VoucherForm(forms.ModelForm):
    class Meta:
        model = Voucher
        fields = [
            'voucher_type',
            'code', 
            'discount_type', 
            'discount_value', 
            'max_discount',
            'valid_from', 
            'valid_to', 
            'is_active',
            'min_purchase_amount',
            'usage_limit',
        ]
        widgets = {
            'voucher_type': forms.Select(attrs={'class': 'form-select'}),
            'code': forms.TextInput(attrs={'placeholder': 'e.g., SUMMER25'}),
            'valid_from': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'valid_to': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'discount_value': forms.NumberInput(attrs={'min': '0', 'step': '0.01', 'placeholder': '10.00'}),
            'max_discount': forms.NumberInput(attrs={'min': '0', 'step': '0.01'}),
            'min_purchase_amount': forms.NumberInput(attrs={'min': '0', 'step': '0.01', 'placeholder': '0.00'}),
            'usage_limit': forms.NumberInput(attrs={'min': '1', 'placeholder': '1'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'voucher_type': 'General vouchers are available to all, dedicated are assigned to specific users.',
            'code': 'Enter a unique code (e.g., SUMMER25) or generate one.',
            'discount_type': 'Percentage takes off a % of the cart total, Fixed removes a specific amount.',
            'discount_value': 'For percentage, enter 1-100. For fixed, enter the amount.',
            'max_discount': 'Optional: Maximum discount amount for percentage discounts.',
            'valid_from': 'Date and time when the voucher becomes active.',
            'valid_to': 'Date and time when the voucher expires.',
            'is_active': 'Uncheck to disable this voucher regardless of dates.',
            'min_purchase_amount': 'Minimum order value required to use this voucher.',
            'usage_limit': 'How many times this voucher can be used in total.',
        }
        labels = {
            'voucher_type': 'Voucher Type',
            'code': 'Voucher Code',
            'discount_type': 'Discount Type',
            'discount_value': 'Discount Value',
            'max_discount': 'Maximum Discount Amount',
            'valid_from': 'Valid From',
            'valid_to': 'Valid To',
            'is_active': 'Is Active',
            'min_purchase_amount': 'Minimum Purchase Amount',
            'usage_limit': 'Usage Limit',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default dates if creating a new voucher
        if not kwargs.get('instance'):
            self.fields['valid_from'].initial = timezone.now().strftime('%Y-%m-%dT%H:%M')
            self.fields['valid_to'].initial = (timezone.now() + timezone.timedelta(days=30)).strftime('%Y-%m-%dT%H:%M')
            self.fields['is_active'].initial = True
            self.fields['usage_limit'].initial = 1
        
        # Add placeholders and help text
        self.fields['code'].widget.attrs.update({'placeholder': 'e.g., SUMMER25'})
        self.fields['min_purchase_amount'].widget.attrs.update({'placeholder': '0.00'})
        self.fields['discount_value'].widget.attrs.update({'placeholder': '10.00'})
        self.fields['usage_limit'].widget.attrs.update({'placeholder': '1'})
        
        # Add help text
        self.fields['voucher_type'].help_text = 'General vouchers are available to all users, dedicated vouchers are assigned to specific users'
        self.fields['discount_type'].help_text = 'Percentage takes off a percentage of the cart total, fixed takes off a specific amount'
        self.fields['max_discount'].help_text = 'Maximum discount amount for percentage discounts'
    
    def clean(self):
        cleaned_data = super().clean()
        valid_from = cleaned_data.get('valid_from')
        valid_to = cleaned_data.get('valid_to')
        discount_type = cleaned_data.get('discount_type')
        discount_value = cleaned_data.get('discount_value')
        max_discount = cleaned_data.get('max_discount')
        
        # Check that valid_to is after valid_from
        if valid_from and valid_to and valid_to <= valid_from:
            raise forms.ValidationError("End date must be after start date.")
        
        # If percentage discount, check that value is between 0 and 100
        if discount_type == 'percentage' and discount_value:
            if discount_value <= 0 or discount_value > 100:
                self.add_error('discount_value', "Percentage discount must be between 0 and 100.")
        
        # If percentage discount, check if max_discount is provided when discount is large
        if discount_type == 'percentage' and discount_value and discount_value > 50 and not max_discount:
            self.add_error('max_discount', "For large percentage discounts, please specify a maximum discount amount.")
        
        return cleaned_data 