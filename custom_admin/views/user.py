from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, SetPasswordForm
from custom_admin.views.dashboard import is_admin
from django import forms
from store.models import UserProfile, Cart, CartItem, CartPackage, Order, ProductRating, PackageRating, ShippingAddress
import secrets
import string

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    is_staff = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    role = forms.ChoiceField(
        required=True, 
        choices=UserProfile.USER_ROLES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'password1', 'password2', 'role')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs['class'] = 'form-control'
        self.fields['password2'].widget.attrs['class'] = 'form-control'

class CustomUserChangeForm(forms.ModelForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    is_active = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    is_staff = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    role = forms.ChoiceField(
        required=True, 
        choices=UserProfile.USER_ROLES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 'role')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.get('instance')
        initial = kwargs.get('initial', {})
        
        # If we have a user instance, get the role from their profile
        if user:
            try:
                profile = UserProfile.objects.get(user=user)
                initial['role'] = profile.role
            except UserProfile.DoesNotExist:
                # Create a profile if it doesn't exist
                profile = UserProfile.objects.create(user=user)
                initial['role'] = profile.role
        
        kwargs['initial'] = initial
        super().__init__(*args, **kwargs)

@user_passes_test(is_admin, login_url='custom_admin:admin_login')
def user_list(request):
    users = User.objects.all().select_related('profile').order_by('-date_joined')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        users = users.filter(username__icontains=search_query) | \
                users.filter(email__icontains=search_query) | \
                users.filter(first_name__icontains=search_query) | \
                users.filter(last_name__icontains=search_query)
    
    # Filter by staff status
    staff_filter = request.GET.get('staff', '')
    if staff_filter == 'staff':
        users = users.filter(is_staff=True)
    elif staff_filter == 'customers':
        users = users.filter(is_staff=False)
    
    # Filter by role
    role_filter = request.GET.get('role', '')
    if role_filter:
        users = users.filter(profile__role=role_filter)
    
    # Pagination
    paginator = Paginator(users, 20)  # Show 20 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'custom_admin/users/list.html', {
        'users': page_obj,
        'search_query': search_query,
        'staff_filter': staff_filter,
        'role_filter': role_filter,
        'roles': UserProfile.USER_ROLES,
    })

@user_passes_test(is_admin, login_url='custom_admin:admin_login')
def user_add(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            # Create the user
            user = form.save()
            
            # Create user profile with the selected role
            profile = UserProfile.objects.create(
                user=user,
                role=form.cleaned_data['role']
            )
            
            messages.success(request, f'User "{user.username}" created successfully with {dict(UserProfile.USER_ROLES)[profile.role]} role.')
            return redirect('admin_dashboard:admin_users')
    else:
        # Default to 'customer' role when creating new users
        form = CustomUserCreationForm(initial={'role': 'customer'})
    
    return render(request, 'custom_admin/users/form.html', {
        'form': form,
        'title': 'Add User',
        'is_add': True,
    })

@user_passes_test(is_admin, login_url='custom_admin:admin_login')
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    
    # Try to get the user profile or create one if it doesn't exist
    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user, role='customer')
    
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, instance=user)
        if form.is_valid():
            # Save the user model
            form.save()
            
            # Update the user profile with the selected role
            profile.role = form.cleaned_data['role']
            profile.save()
            
            messages.success(request, f'User "{user.username}" updated successfully with {dict(UserProfile.USER_ROLES)[profile.role]} role.')
            return redirect('admin_dashboard:admin_users')
    else:
        # Initialize form with user instance and role from profile
        form = CustomUserChangeForm(instance=user, initial={'role': profile.role})
    
    return render(request, 'custom_admin/users/form.html', {
        'form': form,
        'user_obj': user,
        'profile': profile,
        'title': 'Edit User',
        'is_add': False,
    })

@user_passes_test(is_admin, login_url='custom_admin:admin_login')
def user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f'User "{username}" deleted successfully.')
        return redirect('admin_dashboard:admin_users')
    
    return render(request, 'custom_admin/users/delete.html', {
        'user_obj': user,
    })

@user_passes_test(is_admin, login_url='custom_admin:admin_login')
def user_password_reset(request, pk):
    user = get_object_or_404(User, pk=pk)
    
    # Create custom SetPasswordForm with Bootstrap styles
    class CustomSetPasswordForm(SetPasswordForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields['new_password1'].widget.attrs.update({'class': 'form-control'})
            self.fields['new_password2'].widget.attrs.update({'class': 'form-control'})
    
    if request.method == 'POST':
        form = CustomSetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f'Password for "{user.username}" has been reset successfully.')
            return redirect('custom_admin:admin_users')
    else:
        # Generate a random secure password
        alphabet = string.ascii_letters + string.digits + string.punctuation
        suggested_password = ''.join(secrets.choice(alphabet) for _ in range(12))
        form = CustomSetPasswordForm(user)
    
    return render(request, 'custom_admin/users/password_reset.html', {
        'form': form,
        'user_obj': user,
        'suggested_password': suggested_password,
        'title': 'Reset Password',
    })

@user_passes_test(is_admin, login_url='custom_admin:admin_login')
def user_detail(request, pk):
    """Display detailed information about a user for CRM purposes."""
    user = get_object_or_404(User, pk=pk)
    
    # Get user profile
    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user, role='customer')
    
    # Get user's active cart
    try:
        cart = Cart.objects.get(user=user)
        cart_items = CartItem.objects.filter(cart=cart)
        cart_packages = CartPackage.objects.filter(cart=cart)
    except Cart.DoesNotExist:
        cart = None
        cart_items = []
        cart_packages = []
    
    # Get user's orders with pagination
    orders = Order.objects.filter(user=user).order_by('-created_at')
    order_paginator = Paginator(orders, 5)  # Show 5 orders per page
    order_page_number = request.GET.get('order_page')
    order_page_obj = order_paginator.get_page(order_page_number)
    
    # Get user's product ratings
    product_ratings = ProductRating.objects.filter(user=user).select_related('product').order_by('-created_at')
    
    # Get user's package ratings
    package_ratings = PackageRating.objects.filter(user=user).select_related('package').order_by('-created_at')
    
    # Get user's shipping addresses
    shipping_addresses = ShippingAddress.objects.filter(user=user)
    
    return render(request, 'custom_admin/users/detail.html', {
        'user_obj': user,
        'profile': profile,
        'cart': cart,
        'cart_items': cart_items,
        'cart_packages': cart_packages,
        'orders': order_page_obj,
        'product_ratings': product_ratings,
        'package_ratings': package_ratings,
        'shipping_addresses': shipping_addresses,
        'tab': request.GET.get('tab', 'info'),
    })
