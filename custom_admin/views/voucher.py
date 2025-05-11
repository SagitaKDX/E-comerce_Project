from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.contrib.auth.models import User
from django.urls import reverse
from django.http import HttpResponseRedirect, JsonResponse
from django.db.models import Q
from store.models import Voucher, UserVoucher, Notification
from custom_admin.forms.voucher_forms import VoucherForm
from custom_admin.decorators import admin_required
from urllib.parse import urlencode
import random
import string
from collections import Counter

@login_required
@admin_required
def voucher_list(request):
    """Display all vouchers with filtering options"""
    vouchers = Voucher.objects.all().order_by('-created_at')
    
    # Filter by type (general or dedicated)
    voucher_type = request.GET.get('type')
    if voucher_type in ['general', 'dedicated']:
        vouchers = vouchers.filter(voucher_type=voucher_type)
    
    # Filter by status (active, expired)
    status = request.GET.get('status')
    if status == 'active':
        now = timezone.now()
        vouchers = vouchers.filter(
            is_active=True,
            valid_from__lte=now,
            valid_to__gte=now
        )
    elif status == 'expired':
        now = timezone.now()
        vouchers = vouchers.filter(
            Q(is_active=False) | Q(valid_to__lt=now)
        )
    
    # Count vouchers by type
    general_vouchers = sum(1 for v in vouchers if v.voucher_type == 'general')
    dedicated_vouchers = sum(1 for v in vouchers if v.voucher_type == 'dedicated')
    
    # Count active vouchers
    active_vouchers = sum(1 for v in vouchers if v.is_valid)
    
    context = {
        'vouchers': vouchers,
        'active_vouchers': active_vouchers,
        'general_vouchers': general_vouchers,
        'dedicated_vouchers': dedicated_vouchers,
        'total_vouchers': vouchers.count(),
        'title': 'Vouchers',
        'section': 'vouchers',
        'current_filter_type': voucher_type,
        'current_filter_status': status
    }
    return render(request, 'custom_admin/vouchers/voucher_list.html', context)

@login_required
@admin_required
def voucher_add(request):
    """Add a new voucher with improved UI"""
    if request.method == 'POST':
        print("--- VOUCHER ADD POST DATA ---")
        print(request.POST)
        
        # Get the voucher type directly from POST data
        voucher_type = request.POST.get('voucher_type', 'general')
        print(f"Received voucher_type: {voucher_type}")
        
        form = VoucherForm(request.POST)
        if form.is_valid():
            voucher = form.save(commit=False)
            # Ensure voucher type is correctly set from the form data
            voucher.voucher_type = form.cleaned_data['voucher_type'] 
            print(f"Voucher object type before save: {voucher.voucher_type}")
            voucher.save()
            
            print(f"Voucher saved with ID: {voucher.pk} and Type: {voucher.voucher_type}")
            
            # Redirect based on the actual saved voucher type
            if voucher.voucher_type == 'dedicated':
                messages.success(request, f'Dedicated voucher "{voucher.code}" created successfully! Remember to assign it to users.')
                return HttpResponseRedirect(reverse('admin_dashboard:assign_vouchers_to_users') + 
                                          '?' + urlencode({'voucher_ids': str(voucher.pk)}))
            else:
                messages.success(request, f'General voucher "{voucher.code}" created successfully!')
                return redirect('admin_dashboard:admin_vouchers')
        else:
            print("--- FORM ERRORS ---")
            print(form.errors)
            messages.error(request, "Please correct the errors below.")

    else:
        form = VoucherForm(initial={
            'valid_from': timezone.now(),
            'valid_to': timezone.now() + timezone.timedelta(days=30),
            'is_active': True,
            'usage_limit': 1,
            'voucher_type': 'general'
        })
    
    context = {
        'form': form,
        'title': 'Add Voucher',
        'section': 'vouchers'
    }
    return render(request, 'custom_admin/vouchers/voucher_form.html', context)

@login_required
@admin_required
def voucher_edit(request, pk):
    """Edit an existing voucher with improved UI"""
    voucher = get_object_or_404(Voucher, pk=pk)
    
    if request.method == 'POST':
        form = VoucherForm(request.POST, instance=voucher)
        if form.is_valid():
            updated_voucher = form.save()
            
            # If voucher type changed from general to dedicated, offer to assign users
            if 'voucher_type' in form.changed_data and updated_voucher.voucher_type == 'dedicated':
                messages.success(request, f'Voucher "{updated_voucher.code}" updated successfully! This is now a dedicated voucher.')
                return HttpResponseRedirect(reverse('admin_dashboard:assign_vouchers_to_users') + 
                                          '?' + urlencode({'voucher_ids': str(updated_voucher.pk)}))
            
            messages.success(request, f'Voucher "{updated_voucher.code}" updated successfully!')
            return redirect('admin_dashboard:admin_vouchers')
    else:
        form = VoucherForm(instance=voucher)
    
    context = {
        'form': form,
        'voucher': voucher,
        'title': 'Edit Voucher',
        'section': 'vouchers'
    }
    return render(request, 'custom_admin/vouchers/voucher_form.html', context)

@login_required
@admin_required
def voucher_delete(request, pk):
    """Delete a voucher with confirmation"""
    voucher = get_object_or_404(Voucher, pk=pk)
    
    # Check if voucher has been used in orders
    has_user_vouchers = UserVoucher.objects.filter(voucher=voucher).exists()
    
    if request.method == 'POST':
        code = voucher.code
        
        # Delete user voucher associations first
        if has_user_vouchers:
            UserVoucher.objects.filter(voucher=voucher).delete()
            
        # Delete the voucher
        voucher.delete()
        messages.success(request, f'Voucher "{code}" deleted successfully!')
        return redirect('admin_dashboard:admin_vouchers')
    
    context = {
        'voucher': voucher,
        'has_user_vouchers': has_user_vouchers,
        'title': 'Delete Voucher',
        'section': 'vouchers'
    }
    return render(request, 'custom_admin/vouchers/voucher_confirm_delete.html', context)

@login_required
@admin_required
def voucher_duplicate(request, pk):
    """Create a copy of an existing voucher"""
    original_voucher = get_object_or_404(Voucher, pk=pk)
    
    # Create a copy with a new code
    new_code = f"{original_voucher.code}_COPY"
    
    # Check if the new code already exists, if so, add a number
    suffix = 1
    while Voucher.objects.filter(code=new_code).exists():
        new_code = f"{original_voucher.code}_COPY{suffix}"
        suffix += 1
    
    # Create the duplicate voucher
    new_voucher = Voucher.objects.create(
        code=new_code,
        voucher_type=original_voucher.voucher_type,
        discount_type=original_voucher.discount_type,
        discount_value=original_voucher.discount_value,
        max_discount=original_voucher.max_discount,
        valid_from=original_voucher.valid_from,
        valid_to=original_voucher.valid_to,
        is_active=original_voucher.is_active,
        min_purchase_amount=original_voucher.min_purchase_amount,
        usage_limit=original_voucher.usage_limit,
        used_count=0  # Reset usage count
    )
    
    messages.success(request, f'Voucher duplicated successfully! New code: {new_voucher.code}')
    
    # Redirect to edit the new voucher
    return redirect('admin_dashboard:admin_voucher_edit', pk=new_voucher.pk)

@login_required
@admin_required
def assign_vouchers_to_users(request):
    """Assign selected vouchers to users in the custom admin interface"""
    voucher_ids = request.GET.get('voucher_ids', '')
    
    if not voucher_ids:
        messages.error(request, "No vouchers selected for assignment.")
        return redirect('admin_dashboard:admin_vouchers')
    
    # Get the vouchers
    voucher_id_list = [int(id) for id in voucher_ids.split(',') if id.isdigit()]
    vouchers = Voucher.objects.filter(id__in=voucher_id_list, voucher_type='dedicated')
    
    if not vouchers:
        messages.error(request, "Only dedicated vouchers can be assigned to users.")
        return redirect('admin_dashboard:admin_vouchers')
    
    # Get all users
    users = User.objects.filter(is_active=True).order_by('username')
    
    if request.method == 'POST':
        selected_user_ids = request.POST.getlist('users')
        voucher_message = request.POST.get('voucher_message', 'You have received a special voucher!') 
        
        if not selected_user_ids:
            messages.error(request, "No users selected. Please select at least one user.")
        else:
            selected_users = User.objects.filter(id__in=selected_user_ids)
            
            # Create UserVoucher objects
            count = 0
            for voucher in vouchers:
                for user in selected_users:
                    # Check if this user already has this voucher
                    if not UserVoucher.objects.filter(voucher=voucher, user=user).exists():
                        user_voucher = UserVoucher.objects.create(
                            voucher=voucher,
                            user=user,
                            is_used=False,
                            message=voucher_message
                        )
                        count += 1
                        
                        # Create notification for the user
                        Notification.objects.create(
                            user=user,
                            title="You received a new voucher",
                            message=voucher_message,
                            notification_type="promo",
                            reference_id=voucher.id,
                            link=reverse('my_vouchers')
                        )
            
            if count == 0:
                messages.warning(request, "No new voucher assignments were created. Users may already have these vouchers.")
            else:
                messages.success(request, f"Successfully assigned {count} vouchers to users.")
            
            return redirect('admin_dashboard:admin_vouchers')
    
    # Get existing user assignments for these vouchers
    existing_assignments = UserVoucher.objects.filter(voucher__in=vouchers).select_related('user')
    user_assignments = {}
    
    for assignment in existing_assignments:
        if assignment.voucher_id not in user_assignments:
            user_assignments[assignment.voucher_id] = []
        user_assignments[assignment.voucher_id].append(assignment.user.username)
    
    context = {
        'vouchers': vouchers,
        'users': users,
        'user_assignments': user_assignments,
        'title': 'Assign Vouchers to Users',
        'section': 'vouchers'
    }
    
    return render(request, 'custom_admin/vouchers/assign_vouchers.html', context)

@login_required
@admin_required
def check_voucher_code(request):
    """Check if a voucher code already exists - used for AJAX validation"""
    if request.method == 'POST':
        code = request.POST.get('code')
        if not code:
            return JsonResponse({'exists': False, 'message': 'No code provided'})
        
        exists = Voucher.objects.filter(code=code).exists()
        return JsonResponse({
            'exists': exists,
            'message': 'Code already exists' if exists else 'Code is available'
        })
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@login_required
@admin_required
def generate_random_code(request):
    """Generate a unique random voucher code"""
    # Define characters to use in the code
    chars = string.ascii_uppercase + string.digits
    # Remove similar looking characters
    chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
    
    # Try to generate a unique code
    max_attempts = 10
    for _ in range(max_attempts):
        # Generate random code
        random_part = ''.join(random.choice(chars) for _ in range(8))
        code = f"SHOP{random_part}"
        
        # Check if code exists
        if not Voucher.objects.filter(code=code).exists():
            return JsonResponse({'code': code, 'exists': False})
    
    # If we couldn't generate a unique code after max attempts, use timestamp
    timestamp_code = f"SHOP{int(timezone.now().timestamp())}"[-12:]
    return JsonResponse({'code': timestamp_code, 'exists': False})

@login_required
@admin_required
def edit_voucher_users(request, pk):
    """Edit which users a dedicated voucher is assigned to"""
    voucher = get_object_or_404(Voucher, pk=pk)
    
    # Ensure this is a dedicated voucher
    if voucher.voucher_type != 'dedicated':
        messages.error(request, "Only dedicated vouchers can be assigned to specific users.")
        return redirect('admin_dashboard:admin_voucher_edit', pk=voucher.pk)
    
    # Get all active users
    users = User.objects.filter(is_active=True).order_by('username')
    
    # Get currently assigned users
    existing_assignments = UserVoucher.objects.filter(voucher=voucher).select_related('user')
    assigned_user_ids = [assignment.user.id for assignment in existing_assignments]
    
    # Get default message from an existing assignment or use a default
    default_message = ""
    if existing_assignments.exists():
        # Get the most common message from existing assignments
        messages_counter = Counter([a.message for a in existing_assignments if a.message])
        if messages_counter:
            default_message = messages_counter.most_common(1)[0][0]
    
    if not default_message:
        default_message = f"You've received a dedicated voucher: {voucher.code}!"
    
    if request.method == 'POST':
        selected_user_ids = request.POST.getlist('users')
        voucher_message = request.POST.get('voucher_message', default_message)
        
        # Users to add (in selected but not in assigned)
        users_to_add = [int(uid) for uid in selected_user_ids if int(uid) not in assigned_user_ids]
        
        # Users to remove (in assigned but not in selected)
        users_to_remove = [uid for uid in assigned_user_ids if str(uid) not in selected_user_ids]
        
        # Remove users
        if users_to_remove:
            UserVoucher.objects.filter(voucher=voucher, user_id__in=users_to_remove).delete()
        
        # Add new users
        new_assignments_count = 0
        for user_id in users_to_add:
            user = User.objects.get(id=user_id)
            user_voucher = UserVoucher.objects.create(
                voucher=voucher,
                user=user,
                is_used=False,
                message=voucher_message
            )
            new_assignments_count += 1
            
            # Create notification for the user
            Notification.objects.create(
                user=user,
                title="You received a new voucher",
                message=voucher_message,
                notification_type="promo",
                reference_id=voucher.id,
                link=reverse('my_vouchers')
            )
        
        # Update message for existing assignments if it changed
        if voucher_message != default_message:
            for assignment in existing_assignments:
                if assignment.user_id not in users_to_remove:
                    assignment.message = voucher_message
                    assignment.save()
        
        # Show success message
        action_summary = []
        if new_assignments_count > 0:
            action_summary.append(f"added {new_assignments_count} users")
        if users_to_remove:
            action_summary.append(f"removed {len(users_to_remove)} users")
        if voucher_message != default_message:
            action_summary.append("updated the message")
        
        if action_summary:
            messages.success(request, f"Successfully {', '.join(action_summary)}.")
        else:
            messages.info(request, "No changes were made to the voucher assignments.")
        
        return redirect('admin_dashboard:admin_vouchers')
    
    context = {
        'voucher': voucher,
        'users': users,
        'assigned_user_ids': assigned_user_ids,
        'assigned_users_count': len(assigned_user_ids),
        'default_message': default_message,
        'title': 'Edit Voucher Recipients',
        'section': 'vouchers'
    }
    
    return render(request, 'custom_admin/vouchers/voucher_edit_users.html', context) 