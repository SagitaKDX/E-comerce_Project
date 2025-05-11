from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db.models import Count, Sum, F, Q
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from store.models import Product, Category, Comment, CartItem, Order, OrderItem, User
from django.db import connection
from django.urls import reverse
import json
from django.http import JsonResponse

def is_admin(user):
    return user.is_authenticated and user.is_staff

def admin_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('admin_dashboard:dashboard')
        
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None and user.is_staff:
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('admin_dashboard:dashboard')
        else:
            return render(request, 'custom_admin/login.html', {
                'error_message': 'Invalid username or password, or insufficient permissions.'
            })
    
    return render(request, 'custom_admin/login.html')

def admin_logout(request):
    if request.method == 'POST':
        logout(request)
        return redirect('admin_dashboard:admin_login')
    return redirect('admin_dashboard:dashboard')

@user_passes_test(is_admin, login_url='admin_dashboard:admin_login')
def dashboard(request):
    # Add context with dashboard data
    context = {
        'product_count': Product.objects.count(),
        'order_count': Order.objects.count(),
        'customer_count': User.objects.count(),
        'total_revenue': Order.objects.filter(payment_status=True).aggregate(Sum('total_price'))['total_price__sum'] or 0,
        'popular_products': Product.objects.annotate(order_count=Count('orderitem')).order_by('-order_count')[:5],
        'recent_orders': Order.objects.select_related('user').prefetch_related('items').order_by('-created_at')[:5],
    }
    return render(request, 'custom_admin/dashboard.html', context)
