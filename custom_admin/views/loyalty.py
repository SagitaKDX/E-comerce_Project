import uuid
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Q
from django.http import JsonResponse
from django.contrib.auth import get_user_model

from custom_admin.decorators import admin_required
from custom_admin.forms import LoyaltyTierForm, AnniversaryVoucherSettingsForm
from custom_admin.models import LoyaltyTier, CustomerLoyalty, LoyaltyVoucher

User = get_user_model()

@login_required
@admin_required
def loyalty_dashboard(request):
    """Dashboard view for loyalty program stats and management"""
    
    # Get loyalty program overview statistics
    total_users = User.objects.count()
    users_with_tier = CustomerLoyalty.objects.exclude(current_tier=None).count()
    tier_distribution = CustomerLoyalty.objects.values(
        'current_tier__name').annotate(count=Count('id')).order_by('current_tier__minimum_spend')
    
    # Calculate participation rate
    participation_rate = (users_with_tier / total_users * 100) if total_users > 0 else 0
    
    # Get voucher statistics
    total_vouchers = LoyaltyVoucher.objects.count()
    used_vouchers = LoyaltyVoucher.objects.filter(is_used=True).count()
    voucher_usage_rate = (used_vouchers / total_vouchers * 100) if total_vouchers > 0 else 0
    
    # Get tier information
    loyalty_tiers = LoyaltyTier.objects.all().order_by('minimum_spend')
    
    # Get recent tier upgrades
    recent_upgrades = CustomerLoyalty.objects.exclude(tier_updated_at=None).order_by(
        '-tier_updated_at')[:10]
    
    context = {
        'page_title': 'Loyalty Program Dashboard',
        'total_users': total_users,
        'users_with_tier': users_with_tier,
        'participation_rate': round(participation_rate, 2),
        'tier_distribution': tier_distribution,
        'loyalty_tiers': loyalty_tiers,
        'total_vouchers': total_vouchers,
        'used_vouchers': used_vouchers,
        'voucher_usage_rate': round(voucher_usage_rate, 2),
        'recent_upgrades': recent_upgrades,
    }
    
    return render(request, 'custom_admin/loyalty/dashboard.html', context)

@login_required
@admin_required
def loyalty_tiers_list(request):
    """List all loyalty tiers with management options"""
    loyalty_tiers = LoyaltyTier.objects.all().order_by('minimum_spend')
    
    context = {
        'page_title': 'Loyalty Tiers',
        'loyalty_tiers': loyalty_tiers,
    }
    
    return render(request, 'custom_admin/loyalty/tiers_list.html', context)

@login_required
@admin_required
def loyalty_tier_create(request):
    """Create a new loyalty tier"""
    if request.method == 'POST':
        form = LoyaltyTierForm(request.POST)
        if form.is_valid():
            tier = form.save()
            messages.success(request, f'Loyalty tier "{tier.name}" created successfully.')
            return redirect(reverse('admin_dashboard:loyalty_tiers_list'))
    else:
        form = LoyaltyTierForm()
    
    context = {
        'page_title': 'Create Loyalty Tier',
        'form': form,
    }
    
    return render(request, 'custom_admin/loyalty/tier_form.html', context)

@login_required
@admin_required
def loyalty_tier_edit(request, tier_id):
    """Edit an existing loyalty tier"""
    tier = get_object_or_404(LoyaltyTier, id=tier_id)
    
    if request.method == 'POST':
        form = LoyaltyTierForm(request.POST, instance=tier)
        if form.is_valid():
            updated_tier = form.save()
            messages.success(request, f'Loyalty tier "{updated_tier.name}" updated successfully.')
            return redirect(reverse('admin_dashboard:loyalty_tiers_list'))
    else:
        form = LoyaltyTierForm(instance=tier)
    
    context = {
        'page_title': f'Edit Loyalty Tier: {tier.name}',
        'form': form,
        'tier': tier,
    }
    
    return render(request, 'custom_admin/loyalty/tier_form.html', context)

@login_required
@admin_required
def loyalty_tier_delete(request, tier_id):
    """Delete a loyalty tier"""
    tier = get_object_or_404(LoyaltyTier, id=tier_id)
    
    if request.method == 'POST':
        # Count users who are in this tier
        users_count = CustomerLoyalty.objects.filter(current_tier=tier).count()
        
        if users_count > 0:
            messages.error(request, 
                          f'Cannot delete tier "{tier.name}" as it has {users_count} customers assigned. '
                          f'Reassign these customers to another tier first.')
            return redirect(reverse('admin_dashboard:loyalty_tiers_list'))
        
        tier_name = tier.name
        tier.delete()
        messages.success(request, f'Loyalty tier "{tier_name}" deleted successfully.')
        return redirect(reverse('admin_dashboard:loyalty_tiers_list'))
    
    context = {
        'page_title': f'Delete Loyalty Tier: {tier.name}',
        'tier': tier,
        'users_count': CustomerLoyalty.objects.filter(current_tier=tier).count(),
    }
    
    return render(request, 'custom_admin/loyalty/tier_delete.html', context)

@login_required
@admin_required
def loyalty_customers_list(request):
    """List of customers with their loyalty status"""
    search_query = request.GET.get('q', '')
    tier_filter = request.GET.get('tier', '')
    
    customers = CustomerLoyalty.objects.all().select_related('user', 'current_tier')
    
    # Apply filters
    if search_query:
        customers = customers.filter(
            Q(user__username__icontains=search_query) | 
            Q(user__email__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query)
        )
    
    if tier_filter:
        if tier_filter == 'none':
            customers = customers.filter(current_tier=None)
        else:
            customers = customers.filter(current_tier__slug=tier_filter)
    
    # Pagination
    paginator = Paginator(customers.order_by('-total_spend'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get available tiers for filtering
    loyalty_tiers = LoyaltyTier.objects.all().order_by('minimum_spend')
    
    context = {
        'page_title': 'Loyalty Customers',
        'page_obj': page_obj,
        'loyalty_tiers': loyalty_tiers,
        'search_query': search_query,
        'tier_filter': tier_filter,
    }
    
    return render(request, 'custom_admin/loyalty/customers_list.html', context)

@login_required
@admin_required
def customer_loyalty_detail(request, user_id):
    """View and manage loyalty details for a specific customer"""
    user = get_object_or_404(User, id=user_id)
    
    # Get or create loyalty profile
    loyalty, created = CustomerLoyalty.objects.get_or_create(user=user)
    
    # Get customer's vouchers
    vouchers = LoyaltyVoucher.objects.filter(user=user).order_by('-created_at')
    
    # Get all available tiers
    all_tiers = LoyaltyTier.objects.all().order_by('minimum_spend')
    
    # If we're updating tier manually
    if request.method == 'POST' and 'tier_id' in request.POST:
        tier_id = request.POST.get('tier_id')
        if tier_id:
            tier = get_object_or_404(LoyaltyTier, id=tier_id)
            loyalty.current_tier = tier
            loyalty.tier_updated_at = timezone.now()
            loyalty.save()
            messages.success(request, f'{user.username} has been assigned to {tier.name} tier.')
        else:
            loyalty.current_tier = None
            loyalty.save()
            messages.success(request, f'{user.username} has been removed from all tiers.')
            
        return redirect(reverse('admin_dashboard:customer_loyalty_detail', args=[user_id]))
    
    context = {
        'page_title': f'Loyalty Details: {user.username}',
        'user': user,
        'loyalty': loyalty,
        'vouchers': vouchers,
        'all_tiers': all_tiers,
    }
    
    return render(request, 'custom_admin/loyalty/customer_detail.html', context)

@login_required
@admin_required
def create_manual_voucher(request, user_id):
    """Create a manual loyalty voucher for a specific customer"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        amount = request.POST.get('amount')
        voucher_type = request.POST.get('voucher_type')
        valid_days = request.POST.get('valid_days')
        tier_id = request.POST.get('tier_id', None)
        
        try:
            # Validate inputs
            amount = float(amount)
            if amount <= 0:
                raise ValueError("Amount must be greater than zero")
                
            valid_days = int(valid_days)
            if valid_days <= 0:
                raise ValueError("Valid days must be greater than zero")
                
            # Generate a unique code
            code = f"MAN-{user.id}-{uuid.uuid4().hex[:8].upper()}"
            valid_until = timezone.now() + timezone.timedelta(days=valid_days)
            
            # Get tier if specified
            tier = None
            if tier_id:
                tier = get_object_or_404(LoyaltyTier, id=tier_id)
            
            # Create voucher
            voucher = LoyaltyVoucher.objects.create(
                user=user,
                voucher_type=voucher_type,
                tier=tier,
                amount=amount,
                code=code,
                valid_until=valid_until
            )
            
            messages.success(request, f'Voucher {code} created successfully for {user.username}.')
            
        except (ValueError, TypeError) as e:
            messages.error(request, f'Error creating voucher: {str(e)}')
        
        return redirect(reverse('admin_dashboard:customer_loyalty_detail', args=[user_id]))
    
    # Get all tiers for dropdown
    all_tiers = LoyaltyTier.objects.all().order_by('minimum_spend')
    
    context = {
        'page_title': f'Create Voucher for {user.username}',
        'user': user,
        'all_tiers': all_tiers,
    }
    
    return render(request, 'custom_admin/loyalty/create_voucher.html', context)

@login_required
@admin_required
def loyalty_vouchers_list(request):
    """List all loyalty vouchers with management options"""
    search_query = request.GET.get('q', '')
    voucher_type = request.GET.get('type', '')
    status = request.GET.get('status', '')
    
    vouchers = LoyaltyVoucher.objects.all().select_related('user', 'tier')
    
    # Apply filters
    if search_query:
        vouchers = vouchers.filter(
            Q(code__icontains=search_query) | 
            Q(user__username__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )
    
    if voucher_type:
        vouchers = vouchers.filter(voucher_type=voucher_type)
    
    if status:
        if status == 'used':
            vouchers = vouchers.filter(is_used=True)
        elif status == 'unused':
            vouchers = vouchers.filter(is_used=False)
        elif status == 'expired':
            vouchers = vouchers.filter(valid_until__lt=timezone.now(), is_used=False)
        elif status == 'active':
            vouchers = vouchers.filter(valid_until__gte=timezone.now(), is_used=False)
    
    # Pagination
    paginator = Paginator(vouchers.order_by('-created_at'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_title': 'Loyalty Vouchers',
        'page_obj': page_obj,
        'search_query': search_query,
        'voucher_type': voucher_type,
        'status': status,
        'current_time': timezone.now(),
    }
    
    return render(request, 'custom_admin/loyalty/vouchers_list.html', context)

@login_required
@admin_required
def loyalty_settings(request):
    """Manage loyalty program settings"""
    # Load anniversary voucher settings
    try:
        with open('loyalty_settings.json', 'r') as f:
            settings = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        settings = {
            'anniversary_vouchers': {
                'active': True,
                'amount': 10.00,
                'valid_days': 30
            }
        }
    
    if request.method == 'POST':
        form = AnniversaryVoucherSettingsForm(request.POST)
        if form.is_valid():
            # Update anniversary voucher settings
            settings['anniversary_vouchers'] = {
                'active': form.cleaned_data['active'],
                'amount': float(form.cleaned_data['amount']),
                'valid_days': form.cleaned_data['valid_days']
            }
            
            # Save settings to file
            with open('loyalty_settings.json', 'w') as f:
                json.dump(settings, f, indent=4)
                
            messages.success(request, 'Loyalty program settings saved successfully.')
            return redirect(reverse('admin_dashboard:loyalty_settings'))
    else:
        form = AnniversaryVoucherSettingsForm(initial=settings['anniversary_vouchers'])
    
    # Get active tiers count for status
    active_tiers_count = LoyaltyTier.objects.filter(is_active=True).count()
    
    # Get active vouchers count for status
    active_vouchers_count = LoyaltyVoucher.objects.filter(
        is_used=False,
        valid_until__gte=timezone.now()
    ).count()
    
    context = {
        'page_title': 'Loyalty Program Settings',
        'form': form,
        'active_tiers_count': active_tiers_count,
        'active_vouchers_count': active_vouchers_count,
    }
    
    return render(request, 'custom_admin/loyalty/settings.html', context)

@login_required
@admin_required
def recalculate_loyalty_tiers_view(request):
    """Admin view to trigger loyalty tier recalculation"""
    if request.method == 'POST':
        # Direct call instead of using celery task
        from custom_admin.services.loyalty_service import recalculate_all_loyalty_tiers
        try:
            updated_count = recalculate_all_loyalty_tiers()
            messages.success(request, f"Loyalty tier recalculation completed. {updated_count} users were updated.")
        except Exception as e:
            messages.error(request, f"Error during loyalty tier recalculation: {str(e)}")
        return redirect(reverse('admin_dashboard:loyalty_dashboard'))
    
    return render(request, 'custom_admin/loyalty/recalculate_confirmation.html', {
        'page_title': 'Recalculate Loyalty Tiers',
    }) 