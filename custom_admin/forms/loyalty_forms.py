from django import forms
from custom_admin.models import LoyaltyTier

class LoyaltyTierForm(forms.ModelForm):
    """Form for creating and editing loyalty tiers"""
    
    COLOR_CHOICES = [
        ('primary', 'Primary (Blue)'),
        ('secondary', 'Secondary (Gray)'),
        ('success', 'Success (Green)'),
        ('danger', 'Danger (Red)'),
        ('warning', 'Warning (Yellow)'),
        ('info', 'Info (Light Blue)'),
        ('dark', 'Dark (Black)'),
    ]
    
    color_class = forms.ChoiceField(
        choices=COLOR_CHOICES,
        required=True,
        label="Color",
        help_text="The color used to display this tier in the UI"
    )
    
    description = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        label="Description",
        help_text="Optional description of this tier"
    )
    
    benefits = forms.CharField(
        required=False,
        label="Benefits",
        help_text="Comma-separated list of benefits for this tier"
    )
    
    class Meta:
        model = LoyaltyTier
        fields = ['name', 'color_class', 'minimum_spend', 'discount_percentage', 'benefits', 'description', 'is_active']
        widgets = {
            'minimum_spend': forms.NumberInput(attrs={'min': 0, 'step': 0.01}),
            'discount_percentage': forms.NumberInput(attrs={'min': 0, 'max': 100, 'step': 0.1}),
        }
        labels = {
            'name': 'Tier Name',
            'minimum_spend': 'Minimum Spend ($)',
            'discount_percentage': 'Discount Percentage (%)',
            'is_active': 'Active',
        }
        help_texts = {
            'name': 'Name of the loyalty tier (e.g. Silver, Gold, Platinum)',
            'minimum_spend': 'Minimum amount customers must spend to reach this tier',
            'discount_percentage': 'Percentage discount given to customers in this tier',
            'is_active': 'Only active tiers are assigned to customers',
        }

class AnniversaryVoucherSettingsForm(forms.Form):
    """Form for configuring anniversary voucher settings"""
    
    active = forms.BooleanField(
        required=False,
        label="Enable Anniversary Vouchers",
        help_text="Send vouchers to customers on their account anniversary"
    )
    
    amount = forms.DecimalField(
        min_value=0,
        max_value=1000,
        decimal_places=2,
        label="Voucher Amount ($)",
        help_text="Dollar amount for anniversary vouchers"
    )
    
    valid_days = forms.IntegerField(
        min_value=1,
        max_value=365,
        label="Valid Period (days)",
        help_text="Number of days the voucher remains valid after issuance"
    ) 