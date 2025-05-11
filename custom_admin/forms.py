from django import forms
from django.contrib.auth.models import User
from store.models import Category, Product, PromoBanner
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
from store.models import (
    Package, PackageProduct, ShippingCompany, 
    Order, Voucher, UserVoucher
)
from custom_admin.models import FAQ, LoyaltyTier

class PromoBannerForm(forms.ModelForm):
    class Meta:
        model = PromoBanner
        fields = [
            'title', 'subtitle', 'image', 
            'button_text', 'link_type', 'button_link', 
            'text_color', 'button_style', 'caption_position', 'overlay_opacity',
            'active', 'start_date', 'end_date', 'order'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'subtitle': forms.TextInput(attrs={'class': 'form-control'}),
            'button_text': forms.TextInput(attrs={'class': 'form-control'}),
            'link_type': forms.Select(attrs={'class': 'form-control'}),
            'button_link': forms.TextInput(attrs={'class': 'form-control'}),
            'text_color': forms.Select(attrs={'class': 'form-control'}),
            'button_style': forms.Select(attrs={'class': 'form-control'}),
            'caption_position': forms.Select(attrs={'class': 'form-control'}),
            'overlay_opacity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0', 'max': '1'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make image field not required when editing
        if self.instance.pk and self.instance.image:
            self.fields['image'].required = False
        # Only require button_link for custom URLs
        self.fields['button_link'].required = False 

# Product forms
class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'slug', 'description', 'price', 'image', 'category', 'stock', 'is_active', 'is_featured']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'price': forms.NumberInput(attrs={'class': 'form-control'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'is_featured': 'Featured products appear on the homepage.',
        }

# Package forms
class PackageForm(forms.ModelForm):
    class Meta:
        model = Package
        fields = ['name', 'slug', 'description', 'category', 'original_price', 'discounted_price', 'minimum_purchase_amount', 'image', 'is_active', 'is_featured']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'original_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'discounted_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'minimum_purchase_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'original_price': 'Original price (before discount)',
            'discounted_price': 'Selling price (after discount)',
            'minimum_purchase_amount': 'Minimum total value required for customized packages',
            'is_featured': 'Featured packages appear on the homepage.'
        }
    
    def clean(self):
        cleaned_data = super().clean()
        original_price = cleaned_data.get('original_price')
        discounted_price = cleaned_data.get('discounted_price')
        
        if original_price and discounted_price and discounted_price > original_price:
            raise ValidationError("Discounted price cannot be higher than original price.")
        
        return cleaned_data

class PackageProductForm(forms.ModelForm):
    class Meta:
        model = PackageProduct
        fields = ['product', 'quantity', 'is_required']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'is_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class BasePackageProductFormSet(forms.BaseInlineFormSet):
    def is_valid(self):
        # Clean the forms first
        self.clean()
        
        # Only check the validity of forms that are not marked for deletion
        forms_valid = True
        for form in self.forms:
            # Skip forms marked for deletion or empty forms
            if form.cleaned_data.get('DELETE', False):
                continue
                
            # If the form is empty (no product selected), consider it valid
            # This handles the common case of the empty extra form
            if not form.cleaned_data.get('product'):
                if not form.instance.pk:  # Only skip validation if it's a new form
                    continue
                    
            # Check if this individual form is valid
            if not form.is_valid():
                forms_valid = False
        
        return forms_valid and not bool(self._non_form_errors)
    
    def clean(self):
        """
        Custom validation for the formset
        """
        super().clean()
        
        # Skip full validation if there are already errors
        if any(self.errors):
            return
            
        # Check if we have at least one product
        products = []
        has_valid_forms = False
        for form in self.forms:
            # Skip forms without cleaned_data or marked for deletion
            if not hasattr(form, 'cleaned_data') or not form.cleaned_data:
                continue
                
            if form.cleaned_data.get('DELETE', False):
                continue
            
            # Now we know we have at least one valid form
            has_valid_forms = True
            product = form.cleaned_data.get('product')
            
            if not product:
                raise ValidationError("All products must have a product selected.")
                
            quantity = form.cleaned_data.get('quantity')
            if not quantity or quantity < 1:
                raise ValidationError("All products must have a positive quantity.")
                
            products.append(product)
        
        # Ensure we have at least one product
        if not has_valid_forms:
            raise ValidationError("At least one product must be added to the package.")
            
        # Check for duplicate products
        if len(products) != len(set(products)):
            raise ValidationError("Duplicate products are not allowed. Please use the quantity field instead.")

# Create the formset
PackageProductFormSet = inlineformset_factory(
    Package, 
    PackageProduct,
    form=PackageProductForm,
    formset=BasePackageProductFormSet,
    extra=0,
    can_delete=True,
    min_num=1,
    validate_min=True,
)

# Category form
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'slug', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

# Shipping Company form
class ShippingCompanyForm(forms.ModelForm):
    class Meta:
        model = ShippingCompany
        fields = ['name', 'tracking_url', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'tracking_url': forms.URLInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# Admin Login Form
class AdminLoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )

# Voucher Form
class VoucherForm(forms.ModelForm):
    class Meta:
        model = Voucher
        fields = [
            'code', 'discount_type', 'discount_value', 'min_purchase_amount',
            'valid_from', 'valid_to', 'usage_limit', 'voucher_type', 'is_active'
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'discount_type': forms.Select(attrs={'class': 'form-select'}),
            'discount_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'min_purchase_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'valid_from': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'valid_to': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'usage_limit': forms.NumberInput(attrs={'class': 'form-control'}),
            'voucher_type': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        
    def clean(self):
        cleaned_data = super().clean()
        discount_type = cleaned_data.get('discount_type')
        discount_value = cleaned_data.get('discount_value')
        valid_from = cleaned_data.get('valid_from')
        valid_to = cleaned_data.get('valid_to')
        
        if discount_type == 'percentage' and discount_value and discount_value > 100:
            raise ValidationError({'discount_value': 'Percentage discount cannot exceed 100%.'})
            
        if valid_from and valid_to and valid_from > valid_to:
            raise ValidationError({'valid_to': 'End date must be after start date.'})
            
        return cleaned_data

# User Voucher Form
class UserVoucherForm(forms.ModelForm):
    class Meta:
        model = UserVoucher
        fields = ['user', 'voucher', 'is_used']
        widgets = {
            'user': forms.Select(attrs={'class': 'form-select'}),
            'voucher': forms.Select(attrs={'class': 'form-select'}),
            'is_used': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter to show only active vouchers
        self.fields['voucher'].queryset = Voucher.objects.filter(is_active=True)
        # Sort users by username
        self.fields['user'].queryset = User.objects.all().order_by('username')

class FAQForm(forms.ModelForm):
    class Meta:
        model = FAQ
        fields = ['title', 'content', 'order', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 10, 'id': 'markdown-editor'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'content': 'You can use Markdown or LaTeX for formatting. Please refer to Markdown syntax guide for more information.'
        }

class LoyaltyTierForm(forms.ModelForm):
    class Meta:
        model = LoyaltyTier
        fields = ['name', 'minimum_spend', 'description', 'icon', 'badge_color', 
                 'tier_level', 'tier_benefits', 'voucher_amount']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Silver, Gold, Platinum'}),
            'minimum_spend': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Minimum total spend to reach this tier'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Brief description of this tier'}),
            'icon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Font Awesome icon class e.g., fas fa-medal'}),
            'badge_color': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Color code e.g., #3498db'}),
            'tier_level': forms.NumberInput(attrs={'class': 'form-control'}),
            'tier_benefits': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'List benefits, one per line'}),
            'voucher_amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Value of voucher when user reaches this tier'})
        }
    
    def clean(self):
        cleaned_data = super().clean()
        min_spend = cleaned_data.get('minimum_spend')
        
        # Validate if the minimum_spend is greater than lower tiers
        if min_spend:
            instance_id = self.instance.id if self.instance else None
            lower_tier = LoyaltyTier.objects.filter(
                minimum_spend__lt=min_spend
            ).order_by('-minimum_spend').first()
            
            higher_tier = LoyaltyTier.objects.filter(
                minimum_spend__gt=min_spend
            ).order_by('minimum_spend').first()
            
            if lower_tier:
                if lower_tier.tier_level >= int(cleaned_data.get('tier_level')):
                    self.add_error('tier_level', 
                                   f'Tier level must be higher than the "{lower_tier.name}" tier (level {lower_tier.tier_level})')
            
            if higher_tier:
                if higher_tier.tier_level <= int(cleaned_data.get('tier_level')):
                    self.add_error('tier_level', 
                                   f'Tier level must be lower than the "{higher_tier.name}" tier (level {higher_tier.tier_level})')
        
        return cleaned_data

class AnniversaryVoucherSettingsForm(forms.Form):
    active = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    amount = forms.DecimalField(
        min_value=1.00, max_digits=8, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    valid_days = forms.IntegerField(
        min_value=1, initial=30,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial', {})
        # Add defaults if not present
        if 'active' not in initial:
            initial['active'] = True
        if 'amount' not in initial:
            initial['amount'] = 10.00
        if 'valid_days' not in initial:
            initial['valid_days'] = 30
        kwargs['initial'] = initial
        super().__init__(*args, **kwargs) 