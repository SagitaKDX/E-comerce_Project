from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test, login_required
from django.db.models import Count, Q, Avg
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.core.paginator import Paginator
from store.models import Comment, CommentResponse, Product, UserProfile, User, Cart, CartItem, CartPackage, Order, ProductRating, PackageRating, ShippingAddress, Package, PackageProduct, PackageComment, OrderPackage, OrderItem
from django.db import transaction
from datetime import timedelta
from django.contrib.auth import authenticate, login, logout
from django.urls import reverse
import json
import logging
from django.contrib.auth.models import User
from django.db import models

logger = logging.getLogger(__name__)

def is_crm_or_admin(user):
    """Check if user is CRM, staff or admin"""
    if not user.is_authenticated:
        return False
    try:
        return user.profile.is_crm_user() or user.is_staff or user.is_superuser or getattr(user, 'crm_access', False)
    except UserProfile.DoesNotExist:
        return user.is_staff

def is_csr_or_admin(user):
    """Check if user is CSR, staff or admin (higher privileges)"""
    if not user.is_authenticated:
        return False
    try:
        return user.profile.is_csr() or user.is_staff
    except UserProfile.DoesNotExist:
        return user.is_staff

def is_admin(user):
    """Check if user is admin or staff (highest privileges)"""
    if not user.is_authenticated:
        return False
    try:
        return user.profile.role == 'admin' or user.is_staff or user.is_superuser
    except UserProfile.DoesNotExist:
        return user.is_staff or user.is_superuser

def crm_login(request):
    # Handle logout
    if request.GET.get('logout') == 'true':
        logout(request)
        messages.success(request, "You have been logged out successfully.")
        return render(request, 'custom_admin/crm/login.html')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Check if user has CRM or admin role
            try:
                profile = UserProfile.objects.get(user=user)
                if profile.role in ['crm_user', 'csr', 'admin', 'staff']:
                    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                    return redirect('crm:crm_dashboard')
                else:
                    messages.error(request, "You don't have permission to access the CRM system.")
            except UserProfile.DoesNotExist:
                messages.error(request, "User profile not found.")
        else:
            messages.error(request, "Invalid username or password.")
    
    return render(request, 'custom_admin/crm/login.html')

@login_required(login_url='crm:crm_login')
@user_passes_test(is_crm_or_admin, login_url='crm:crm_login')
def crm_dashboard(request):
    """
    CRM Dashboard showing comment metrics and recent comments
    """
    # Get statistics for dashboard
    total_comments = Comment.objects.count()
    new_count = Comment.objects.filter(status='new').count()
    in_progress_count = Comment.objects.filter(status='in_progress').count()
    resolved_count = Comment.objects.filter(status='resolved').count()
    closed_count = Comment.objects.filter(status='closed').count()
    
    # Recent comments
    recent_comments = Comment.objects.select_related('user', 'product').order_by('-created_at')[:5]
    
    # Comments assigned to current user
    assigned_comments = Comment.objects.filter(
        assigned_to=request.user
    ).select_related('user', 'product').order_by('-created_at')[:5]
    
    # Recent product ratings
    recent_product_ratings = ProductRating.objects.select_related(
        'user', 'product'
    ).order_by('-created_at')[:5]
    
    # Get new product ratings from the last 24 hours
    one_day_ago = timezone.now() - timedelta(days=1)
    new_product_ratings = ProductRating.objects.select_related(
        'user', 'product'
    ).filter(
        created_at__gte=one_day_ago
    ).order_by('-created_at')[:10]
    
    # Count of new ratings in the last 24 hours
    new_ratings_count = ProductRating.objects.filter(
        created_at__gte=one_day_ago
    ).count()
    
    # Recent package ratings
    recent_package_ratings = PackageRating.objects.select_related(
        'user', 'package'
    ).order_by('-created_at')[:5]
    
    # Get new package ratings from the last 24 hours
    new_package_ratings = PackageRating.objects.select_related(
        'user', 'package'
    ).filter(
        created_at__gte=one_day_ago
    ).order_by('-created_at')[:10]
    
    # Calculate average response time
    comments_with_response = Comment.objects.filter(
        responses__isnull=False
    ).distinct()
    
    avg_response_time = None
    if comments_with_response.exists():
        total_time = timedelta()
        count = 0
        
        for comment in comments_with_response:
            first_response = comment.responses.order_by('created_at').first()
            if first_response:
                response_time = first_response.created_at - comment.created_at
                total_time += response_time
                count += 1
        
        if count > 0:
            avg_seconds = total_time.total_seconds() / count
            avg_hours = avg_seconds / 3600
            avg_response_time = round(avg_hours, 1)
    
    # Calculate average resolution time
    resolved_comments = Comment.objects.filter(status__in=['resolved', 'closed'])
    avg_resolution_time = None
    if resolved_comments.exists():
        total_time = timedelta()
        count = 0
        
        for comment in resolved_comments:
            if comment.updated_at > comment.created_at:
                resolution_time = comment.updated_at - comment.created_at
                total_time += resolution_time
                count += 1
        
        if count > 0:
            avg_seconds = total_time.total_seconds() / count
            avg_hours = avg_seconds / 3600
            avg_resolution_time = round(avg_hours, 1)
    
    context = {
        'total_count': total_comments,
        'new_count': new_count,
        'in_progress_count': in_progress_count,
        'resolved_count': resolved_count,
        'closed_count': closed_count,
        'recent_comments': recent_comments,
        'assigned_comments': assigned_comments,
        'recent_product_ratings': recent_product_ratings,
        'recent_package_ratings': recent_package_ratings,
        'new_product_ratings': new_product_ratings,
        'new_package_ratings': new_package_ratings,
        'new_ratings_count': new_ratings_count,
        'avg_response_time': avg_response_time,
        'avg_resolution_time': avg_resolution_time,
    }
    
    return render(request, 'custom_admin/crm/dashboard.html', context)

@login_required(login_url='crm:crm_login')
@user_passes_test(is_crm_or_admin, login_url='crm:crm_login')
def comment_list(request):
    """
    List all comments with filtering options
    """
    comments = Comment.objects.select_related('user', 'product', 'assigned_to').order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter and status_filter != 'all':
        comments = comments.filter(status=status_filter)
    
    # Filter by assignment
    assignment_filter = request.GET.get('assignment')
    if assignment_filter == 'assigned_to_me':
        comments = comments.filter(assigned_to=request.user)
    elif assignment_filter == 'unassigned':
        comments = comments.filter(assigned_to__isnull=True)
    
    # Filter by search term
    search_term = request.GET.get('search')
    if search_term:
        comments = comments.filter(
            Q(text__icontains=search_term) |
            Q(user__username__icontains=search_term) |
            Q(product__name__icontains=search_term)
        )
    
    # Calculate response time for each comment
    now = timezone.now()
    for comment in comments:
        first_response = comment.responses.order_by('created_at').first()
        if first_response:
            response_time = first_response.created_at - comment.created_at
            comment.response_time_hours = round(response_time.total_seconds() / 3600, 1)
            comment.has_response = True
        else:
            comment.has_response = False
            if comment.status == 'new':
                # Calculate time since creation for unresponded comments
                waiting_time = now - comment.created_at
                comment.waiting_time_hours = round(waiting_time.total_seconds() / 3600, 1)
    
    # Pagination
    paginator = Paginator(comments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'assignment_filter': assignment_filter,
        'search_term': search_term,
    }
    
    return render(request, 'custom_admin/crm/comment_list.html', context)

@login_required(login_url='crm:crm_login')
@user_passes_test(is_csr_or_admin, login_url='crm:crm_login')
def comment_detail(request, pk):
    """
    View a single comment with its responses and manage it
    """
    comment = get_object_or_404(Comment.objects.select_related('user', 'product', 'assigned_to'), pk=pk)
    responses = comment.responses.select_related('user').order_by('created_at')
    
    # Calculate response metrics
    now = timezone.now()
    first_response = responses.first()
    if first_response:
        response_time = first_response.created_at - comment.created_at
        comment.response_time_hours = round(response_time.total_seconds() / 3600, 1)
        comment.response_time_minutes = round(response_time.total_seconds() / 60, 1)
        comment.has_response = True
    else:
        comment.has_response = False
        waiting_time = now - comment.created_at
        comment.waiting_time_hours = round(waiting_time.total_seconds() / 3600, 1)
        comment.waiting_time_minutes = round(waiting_time.total_seconds() / 60, 1)
    
    if comment.status in ['resolved', 'closed']:
        resolution_time = comment.updated_at - comment.created_at
        comment.resolution_time_hours = round(resolution_time.total_seconds() / 3600, 1)
        comment.resolution_time_days = round(resolution_time.total_seconds() / (3600 * 24), 1)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'respond':
            response_text = request.POST.get('response')
            is_private = request.POST.get('is_private') == 'on'
            
            if response_text:
                CommentResponse.objects.create(
                    comment=comment,
                    user=request.user,
                    text=response_text,
                    is_private=is_private
                )
                
                # If this is the first response and comment is new, update status
                if comment.status == 'new':
                    comment.status = 'in_progress'
                    comment.save()
                
                messages.success(request, 'Response added successfully.')
            else:
                messages.error(request, 'Response text is required.')
                
        elif action == 'update_status':
            new_status = request.POST.get('status')
            if new_status in dict(Comment.STATUS_CHOICES).keys():
                comment.status = new_status
                comment.save()
                messages.success(request, f'Status updated to {dict(Comment.STATUS_CHOICES)[new_status]}.')
            
        elif action == 'assign':
            assign_to = request.POST.get('assign_to')
            if assign_to == 'me':
                comment.assigned_to = request.user
                comment.save()
                messages.success(request, 'Comment assigned to you.')
            elif assign_to == 'unassign':
                comment.assigned_to = None
                comment.save()
                messages.success(request, 'Comment unassigned.')
        
        return redirect('crm:crm_comment_detail', pk=comment.pk)
    
    # Get CRMs for assignment dropdown
    crms = User.objects.filter(
        Q(profile__role__in=['csr', 'admin', 'staff']) | Q(is_staff=True)
    ).distinct()
    
    context = {
        'comment': comment,
        'responses': responses,
        'crms': crms,
    }
    
    return render(request, 'custom_admin/crm/comment_detail.html', context)

@login_required(login_url='crm:crm_login')
@user_passes_test(is_crm_or_admin, login_url='crm:crm_login')
def crm_analytics(request):
    """
    Analytics dashboard for CRM metrics
    """
    # Get data for last 30 days
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    # Comments by status
    status_counts = Comment.objects.filter(
        created_at__gte=thirty_days_ago
    ).values('status').annotate(count=Count('id')).order_by('status')
    
    # Comments over time (daily)
    daily_counts = Comment.objects.filter(
        created_at__gte=thirty_days_ago
    ).extra({
        'date': 'date(created_at)'
    }).values('date').annotate(count=Count('id')).order_by('date')
    
    # Resolution time metrics
    resolution_times = []
    resolved_comments = Comment.objects.filter(
        status__in=['resolved', 'closed'],
        updated_at__gte=thirty_days_ago
    )
    
    for comment in resolved_comments:
        resolution_time = (comment.updated_at - comment.created_at).total_seconds() / 3600  # in hours
        resolution_times.append(resolution_time)
    
    avg_resolution_time = sum(resolution_times) / len(resolution_times) if resolution_times else 0
    
    # Calculate resolution rate
    total_comments_30d = Comment.objects.filter(created_at__gte=thirty_days_ago).count()
    resolved_comments_30d = Comment.objects.filter(
        status__in=['resolved', 'closed'],
        updated_at__gte=thirty_days_ago
    ).count()
    
    resolution_rate = (resolved_comments_30d / total_comments_30d * 100) if total_comments_30d > 0 else 0
    
    context = {
        'status_counts': status_counts,
        'daily_counts': daily_counts,
        'avg_resolution_time': avg_resolution_time,
        'total_comments_30d': total_comments_30d,
        'resolved_comments_30d': resolved_comments_30d,
        'resolution_rate': resolution_rate,
    }
    
    return render(request, 'custom_admin/crm/analytics.html', context)

@login_required(login_url='crm:crm_login')
@user_passes_test(is_csr_or_admin, login_url='crm:crm_login')
def crm_settings(request):
    """
    Settings page for CRM system
    """
    if request.method == 'POST':
        # Update user preferences or CRM settings
        messages.success(request, 'Settings updated successfully.')
        return redirect('crm:crm_settings')
    
    return render(request, 'custom_admin/crm/settings.html')

@login_required
def crm_user_detail(request, pk):
    """Display detailed information about a user in the CRM system."""
    if not is_crm_or_admin(request.user):
        messages.error(request, "You do not have access to this area.")
        return redirect('store:home')
    
    # Get the user and their profile
    user = get_object_or_404(User.objects.select_related('profile'), pk=pk)
    
    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        profile = None
    
    # Get the user's cart with prefetched items
    try:
        cart = Cart.objects.filter(user=user).order_by('-created_at').first()
        if cart:
            cart_items = CartItem.objects.filter(cart=cart).select_related('product')
            cart_packages = CartPackage.objects.filter(cart=cart).select_related('package')
        else:
            cart_items = []
            cart_packages = []
    except Cart.DoesNotExist:
        cart = None
        cart_items = []
        cart_packages = []
    
    # Get the user's orders with pagination and prefetch related items
    orders = Order.objects.filter(user=user).prefetch_related('items', 'items__product').order_by('-created_at')
    
    # Get all orders for summary statistics (without pagination)
    total_orders_count = orders.count()
    total_order_value = sum(order.total_price for order in orders)
    
    # Paginate orders for display
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    orders_page = paginator.get_page(page_number)
    
    # Get the user's product and package ratings with related products
    product_ratings = ProductRating.objects.filter(user=user).select_related('product').order_by('-created_at')
    package_ratings = PackageRating.objects.filter(user=user).select_related('package').order_by('-created_at')
    
    # Get ratings statistics
    total_ratings_count = product_ratings.count() + package_ratings.count()
    avg_product_rating = product_ratings.values_list('rating', flat=True).aggregate(avg=models.Avg('rating'))['avg'] or 0
    
    # Pre-calculate counts for each rating level
    rating_counts = {
        5: 0,
        4: 0,
        3: 0,
        2: 0,
        1: 0
    }
    
    for rating in product_ratings:
        if rating.rating in rating_counts:
            rating_counts[rating.rating] += 1
    
    # Get the user's shipping addresses
    shipping_addresses = ShippingAddress.objects.filter(user=user)
    
    context = {
        'user_detail': user,  # Using user_detail to avoid conflict with request.user
        'profile': profile,
        'cart': cart,
        'cart_items': cart_items,
        'cart_packages': cart_packages,
        'orders': orders_page,
        'product_ratings': product_ratings,
        'package_ratings': package_ratings,
        'shipping_addresses': shipping_addresses,
        # Additional summary statistics
        'total_orders_count': total_orders_count,
        'total_order_value': total_order_value,
        'total_ratings_count': total_ratings_count,
        'avg_product_rating': avg_product_rating,
        # Add pre-calculated rating counts
        'rating_counts': rating_counts,
    }
    
    return render(request, 'custom_admin/crm/users/detail.html', context)

@login_required
def crm_user_list(request):
    """Display a list of all users in the CRM system (view only)."""
    if not is_crm_or_admin(request.user):
        messages.error(request, "You do not have access to this area.")
        return redirect('store:home')

    # Get filter parameters
    search_term = request.GET.get('search', '')
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    date_start_str = request.GET.get('date_joined_start', '')
    date_end_str = request.GET.get('date_joined_end', '')

    # Start with all users, prefetch profile for efficiency
    users = User.objects.all().select_related('profile').order_by('-date_joined')

    # Apply text search filter
    if search_term:
        users = users.filter(
            Q(username__icontains=search_term) |
            Q(email__icontains=search_term) |
            Q(first_name__icontains=search_term) |
            Q(last_name__icontains=search_term)
        )

    # Apply role filter
    if role_filter:
        users = users.filter(profile__role=role_filter)

    # Apply status filter
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)

    # Apply date joined filter
    date_start = None
    if date_start_str:
        try:
            date_start = timezone.datetime.strptime(date_start_str, '%Y-%m-%d').date()
            users = users.filter(date_joined__date__gte=date_start)
        except ValueError:
            messages.warning(request, "Invalid start date format. Please use YYYY-MM-DD.")

    date_end = None
    if date_end_str:
        try:
            date_end = timezone.datetime.strptime(date_end_str, '%Y-%m-%d').date()
            # Add a day to end_date to make it inclusive for __lte
            # users = users.filter(date_joined__date__lte=date_end + timezone.timedelta(days=1)) # Alternative: use date range
            users = users.filter(date_joined__date__lte=date_end)
        except ValueError:
            messages.warning(request, "Invalid end date format. Please use YYYY-MM-DD.")

    # Pagination
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Build filter params for pagination links
    filter_params = request.GET.copy()
    if 'page' in filter_params:
        del filter_params['page']
    filter_query_string = filter_params.urlencode()

    context = {
        'page_obj': page_obj,
        'roles': UserProfile.USER_ROLES,
        # Pass filter values back to template
        'search_term': search_term,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'date_start': date_start_str, # Pass original string back
        'date_end': date_end_str, # Pass original string back
        'filter_params': '&' + filter_query_string if filter_query_string else '' # For pagination links
    }

    return render(request, 'custom_admin/crm/users/list.html', context)

@login_required
def crm_user_add(request):
    """Add a new user from the CRM system with automatic verification."""
    if not is_crm_or_admin(request.user):
        messages.error(request, "You do not have access to this area.")
        return redirect('store:home')
    
    from django import forms
    
    class CRMUserCreationForm(forms.Form):
        username = forms.CharField(required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
        email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
        first_name = forms.CharField(required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
        last_name = forms.CharField(required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
        password1 = forms.CharField(
            label="Password",
            required=True, 
            widget=forms.PasswordInput(attrs={'class': 'form-control'})
        )
        password2 = forms.CharField(
            label="Confirm Password",
            required=True, 
            widget=forms.PasswordInput(attrs={'class': 'form-control'})
        )
        role = forms.CharField(
            required=True,
            initial='customer',
            widget=forms.HiddenInput()
        )

        def clean(self):
            cleaned_data = super().clean()
            password1 = cleaned_data.get('password1')
            password2 = cleaned_data.get('password2')
            username = cleaned_data.get('username')
            email = cleaned_data.get('email')
            
            if password1 and password2 and password1 != password2:
                self.add_error('password2', "The two password fields didn't match.")
            
            # Check if username already exists
            if User.objects.filter(username=username).exists():
                self.add_error('username', "A user with that username already exists.")
            
            # Check if email already exists
            if User.objects.filter(email=email).exists():
                self.add_error('email', "A user with that email already exists.")
                
            return cleaned_data
            
    if request.method == 'POST':
        form = CRMUserCreationForm(request.POST)
        if form.is_valid():
            # Create user
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password1'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name']
            )
            
            # Create or update user profile with verified email
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.role = form.cleaned_data['role']
            profile.is_email_verified = True  # Auto-verify email
            profile.save()
            
            messages.success(request, f'User "{user.username}" created successfully with verified email.')
            return redirect('crm:crm_user_list')
    else:
        form = CRMUserCreationForm()
    
    return render(request, 'custom_admin/crm/users/form.html', {
        'form': form,
        'title': 'Add New User'
    })

@login_required
def crm_order_list(request):
    """Display a list of all orders in the CRM system (view only)."""
    if not is_crm_or_admin(request.user):
        messages.error(request, "You do not have access to this area.")
        return redirect('store:home')
    
    orders = Order.objects.all().order_by('-created_at')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        orders = orders.filter(id__icontains=search_query) | \
                orders.filter(user__username__icontains=search_query) | \
                orders.filter(user__email__icontains=search_query)
    
    # Filter by status
    status = request.GET.get('status', '')
    if status:
        orders = orders.filter(status=status)
    
    # Filter by date range
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    if start_date and end_date:
        try:
            start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d')
            end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d')
            # Add a day to end_date to make it inclusive
            end_date = end_date + timezone.timedelta(days=1)
            orders = orders.filter(created_at__range=[start_date, end_date])
        except ValueError:
            messages.error(request, 'Invalid date format. Please use YYYY-MM-DD.')
    
    # Calculate the total value of all filtered orders
    total_value = sum(order.total_price for order in orders)
    
    # Pagination
    paginator = Paginator(orders, 20)  # Show 20 orders per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get unique statuses for filter dropdown
    statuses = Order.objects.values_list('status', flat=True).distinct()
    
    context = {
        'orders': page_obj,
        'search_query': search_query,
        'status_filter': status,
        'start_date': start_date,
        'end_date': end_date,
        'statuses': statuses,
        'total_value': total_value,
    }
    
    return render(request, 'custom_admin/crm/orders/list.html', context)

@login_required
def crm_order_detail(request, pk):
    """Display detailed information about an order in the CRM system (view only)."""
    if not is_crm_or_admin(request.user):
        messages.error(request, "You do not have access to this area.")
        return redirect('store:home')
    
    order = get_object_or_404(Order, pk=pk)
    
    context = {
        'order': order,
    }
    
    return render(request, 'custom_admin/crm/orders/detail.html', context)

@login_required
@user_passes_test(is_admin)
def crm_package_detail(request, pk):
    package = get_object_or_404(Package, pk=pk)
    package_products = PackageProduct.objects.filter(package=package).select_related('product')
    
    # Get ratings and calculate statistics
    ratings = PackageRating.objects.filter(package=package).select_related('user')
    total_ratings = ratings.count()
    avg_rating = ratings.aggregate(avg=Avg('rating'))['avg'] or 0
    
    # Calculate rating distribution
    rating_counts = {
        '5': ratings.filter(rating=5).count(),
        '4': ratings.filter(rating=4).count(),
        '3': ratings.filter(rating=3).count(),
        '2': ratings.filter(rating=2).count(),
        '1': ratings.filter(rating=1).count()
    }
    
    # Get recent comments
    comments = PackageComment.objects.filter(package=package).select_related('user').order_by('-created_at')
    
    context = {
        'package': package,
        'package_products': package_products,
        'ratings': ratings,
        'total_ratings': total_ratings,
        'avg_rating': avg_rating,
        'rating_counts': rating_counts,
        'comments': comments
    }
    
    return render(request, 'custom_admin/crm/packages/detail.html', context)

@login_required
@user_passes_test(is_admin)
def crm_product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    
    # Get ratings and calculate statistics
    ratings = ProductRating.objects.filter(product=product).select_related('user')
    total_ratings = ratings.count()
    avg_rating = ratings.aggregate(avg=Avg('rating'))['avg'] or 0
    
    # Calculate rating distribution
    rating_counts = {
        '5': ratings.filter(rating=5).count(),
        '4': ratings.filter(rating=4).count(),
        '3': ratings.filter(rating=3).count(),
        '2': ratings.filter(rating=2).count(),
        '1': ratings.filter(rating=1).count()
    }
    
    # Get recent comments
    comments = Comment.objects.filter(product=product).select_related('user').order_by('-created_at')
    
    context = {
        'product': product,
        'ratings': ratings,
        'total_ratings': total_ratings,
        'avg_rating': avg_rating,
        'rating_counts': rating_counts,
        'comments': comments
    }
    
    return render(request, 'custom_admin/crm/products/detail.html', context)

@login_required
@user_passes_test(is_admin)
def crm_package_list(request):
    packages = Package.objects.all().select_related('category')
    
    # Calculate average ratings
    for package in packages:
        ratings = PackageRating.objects.filter(package=package)
        package.avg_rating = ratings.aggregate(avg=Avg('rating'))['avg'] or 0
        package.sold_count = OrderPackage.objects.filter(package=package).count()
    
    # Pagination
    paginator = Paginator(packages, 10)
    page = request.GET.get('page')
    packages = paginator.get_page(page)
    
    context = {
        'packages': packages
    }
    
    return render(request, 'custom_admin/crm/packages/list.html', context)

@login_required
@user_passes_test(is_admin)
def crm_product_list(request):
    products = Product.objects.all().select_related('category')
    
    # Calculate average ratings
    for product in products:
        ratings = ProductRating.objects.filter(product=product)
        product.avg_rating = ratings.aggregate(avg=Avg('rating'))['avg'] or 0
        product.sold_count = OrderItem.objects.filter(product=product).count()
    
    # Pagination
    paginator = Paginator(products, 10)
    page = request.GET.get('page')
    products = paginator.get_page(page)
    
    context = {
        'products': products
    }
    
    return render(request, 'custom_admin/crm/products/list.html', context)

@login_required
@user_passes_test(is_csr_or_admin)
def mark_product_rating_reviewed(request, rating_id):
    """Mark a product rating as reviewed by staff"""
    if request.method == 'POST':
        rating = get_object_or_404(ProductRating, id=rating_id)
        
        # Mark as reviewed
        rating.staff_reviewed = True
        rating.save()
        
        messages.success(request, f"Rating #{rating_id} for {rating.product.name} marked as reviewed")
        
        # Redirect back to the referrer or to product detail page
        next_url = request.POST.get('next') or reverse('crm:crm_product_detail', kwargs={'pk': rating.product.id})
        return redirect(next_url)
    
    # If not POST, redirect to dashboard
    return redirect('crm:crm_dashboard')

@login_required
@user_passes_test(is_csr_or_admin)
def mark_package_rating_reviewed(request, rating_id):
    """Mark a package rating as reviewed by staff"""
    if request.method == 'POST':
        rating = get_object_or_404(PackageRating, id=rating_id)
        
        # Mark as reviewed
        rating.staff_reviewed = True
        rating.save()
        
        messages.success(request, f"Rating #{rating_id} for {rating.package.name} marked as reviewed")
        
        # Redirect back to the referrer or to package detail page
        next_url = request.POST.get('next') or reverse('crm:crm_package_detail', kwargs={'pk': rating.package.id})
        return redirect(next_url)
    
    # If not POST, redirect to dashboard
    return redirect('crm:crm_dashboard') 