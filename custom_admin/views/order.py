from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from store.models import Order  # Assuming you have an Order model
from custom_admin.views.dashboard import is_admin
from django import forms
from django.utils import timezone
from django.urls import reverse

class OrderStatusForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

@user_passes_test(is_admin, login_url='custom_admin:admin_login')
def order_list(request):
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
    
    # Pagination
    paginator = Paginator(orders, 20)  # Show 20 orders per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get unique statuses for filter dropdown
    statuses = Order.objects.values_list('status', flat=True).distinct()
    
    return render(request, 'custom_admin/orders/list.html', {
        'orders': page_obj,
        'search_query': search_query,
        'status_filter': status,
        'start_date': start_date,
        'end_date': end_date,
        'statuses': statuses,
    })

@user_passes_test(is_admin, login_url='custom_admin:admin_login')
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)
    
    return render(request, 'custom_admin/orders/detail.html', {
        'order': order,
    })

@user_passes_test(is_admin, login_url='custom_admin:admin_login')
def order_update(request, pk):
    order = get_object_or_404(Order, pk=pk)
    original_status = order.status
    
    if request.method == 'POST':
        form = OrderStatusForm(request.POST, instance=order)
        if form.is_valid():
            new_status = form.cleaned_data['status']
            print(f"DEBUG: Order status update - ID #{order.id}, FROM: {original_status}, TO: {new_status}")
            
            # Only process inventory/voucher changes when moving to a "processed" state
            # from a non-processed state or if inventory wasn't adjusted yet
            inventory_was_adjusted = getattr(order, 'inventory_adjusted', False)
            stock_should_be_updated = (
                new_status in ['processing', 'shipped', 'delivered'] and 
                (original_status == 'pending' or not inventory_was_adjusted)
            )
            
            if stock_should_be_updated:
                print(f"DEBUG: Will adjust inventory for order #{order.id}")
                print(f"DEBUG: Previous inventory_adjusted flag: {inventory_was_adjusted}")
                
                # Use a flag on the order to track if inventory was adjusted
                # We'll attach this temporarily to the instance for tracking within this request
                setattr(order, 'inventory_adjusted', True)
                
                # Update product inventory
                try:
                    print(f"DEBUG: Processing inventory updates for order #{order.id}")
                    order_items = list(order.items.all())
                    print(f"DEBUG: Found {len(order_items)} items to update")
                    
                    for item in order_items:
                        try:
                            from django.db import transaction
                            
                            # Use transaction to ensure changes are saved
                            with transaction.atomic():
                                product = item.product
                                original_stock = product.stock
                                print(f"DEBUG: Updating product #{product.id} ({product.name})")
                                print(f"DEBUG: Current stock: {original_stock}, Quantity ordered: {item.quantity}")
                                
                                if product.stock < item.quantity:
                                    print(f"WARNING: Product {product.id} has insufficient stock ({product.stock} < {item.quantity})")
                                    messages.warning(request, f"Warning: Product '{product.name}' has insufficient stock ({product.stock} < {item.quantity})")
                                
                                # Decrease stock - directly update the database for maximum consistency
                                from django.db.models import F
                                update_count = type(product).objects.filter(pk=product.pk).update(
                                    stock=F('stock') - item.quantity
                                )
                                
                                print(f"DEBUG: Direct DB update affected {update_count} product records")
                                
                                # Get refreshed version from DB to confirm changes
                                refreshed_product = type(product).objects.get(pk=product.pk)
                                print(f"DEBUG: Verified stock update: was {original_stock}, now {refreshed_product.stock}")
                                
                                # Update the current product instance to match DB
                                product.stock = refreshed_product.stock
                        except Exception as e:
                            print(f"ERROR updating product {getattr(item, 'product_id', 'unknown')}: {str(e)}")
                            messages.error(request, f"Error updating product stock: {str(e)}")
                    
                    # Add a field to order to indicate inventory was adjusted
                    # We need to store this in the database too
                    if not hasattr(Order, 'inventory_adjusted'):
                        try:
                            # Try to read inventory_adjusted directly from DB if exists
                            print("DEBUG: Checking if inventory_adjusted field exists in Order model")
                            from django.db import connection
                            with connection.cursor() as cursor:
                                cursor.execute("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_NAME='store_order' AND COLUMN_NAME='inventory_adjusted'")
                                field_exists = cursor.fetchone()[0] > 0
                            
                            if not field_exists:
                                print("DEBUG: inventory_adjusted field doesn't exist in database")
                                # Use order notes to track inventory adjustment if field doesn't exist
                                if not order.order_notes:
                                    order.order_notes = ""
                                if "[INVENTORY ADJUSTED]" not in order.order_notes:
                                    order.order_notes += " [INVENTORY ADJUSTED]"
                                    print("DEBUG: Added [INVENTORY ADJUSTED] tag to order notes")
                        except Exception as e:
                            print(f"ERROR checking inventory_adjusted field: {str(e)}")
                    
                    print(f"DEBUG: All product stocks updated successfully for order #{order.id}")
                except Exception as e:
                    print(f"ERROR in product stock update process: {str(e)}")
                    messages.error(request, f"Error updating product stock: {str(e)}")
                
                # Mark voucher as used if applicable
                if order.voucher and not order.voucher.is_used:
                    try:
                        print(f"DEBUG: Marking voucher {order.voucher.voucher.code} as used")
                        order.voucher.use_voucher()  # This increments voucher.voucher.used_count and marks UserVoucher as used
                        print(f"DEBUG: Voucher marked as used successfully")
                    except Exception as e:
                        print(f"ERROR marking voucher as used: {str(e)}")
                        messages.error(request, f"Error marking voucher as used: {str(e)}")
            
            # Don't revert inventory changes if order is cancelled
            # (inventory management would need to be done manually for cancelled orders)
            
            # Save the updated order
            updated_order = form.save()
            
            # Send notification to customer about status update
            if request.POST.get('notify_customer') == 'on':
                from store.models import Notification
                
                # Create appropriate message based on status
                if new_status == 'processing':
                    message = f"Your order #{order.id} is now being processed."
                elif new_status == 'shipped':
                    message = f"Your order #{order.id} has been shipped."
                elif new_status == 'delivered':
                    message = f"Your order #{order.id} has been delivered."
                elif new_status == 'cancelled':
                    message = f"Your order #{order.id} has been cancelled."
                else:
                    message = f"Your order #{order.id} status has been updated to {new_status}."
                
                # Add the notes if provided
                notes = request.POST.get('notes')
                if notes:
                    message += f" Note: {notes}"
                
                # Create notification
                try:
                    Notification.objects.create(
                        user=order.user,
                        title=f"Order {new_status.title()}",
                        message=message,
                        notification_type="order",
                        reference_id=order.id,
                        link=reverse('order_detail', kwargs={'order_id': order.id})
                    )
                    print(f"DEBUG: Notification created successfully for user {order.user.username}")
                except Exception as e:
                    print(f"ERROR creating notification: {str(e)}")
                    messages.error(request, f"Error sending notification to customer: {str(e)}")
            
            messages.success(request, f'Order #{order.id} status updated successfully.')
            return redirect('admin_dashboard:admin_order_detail', pk=order.id)
    else:
        form = OrderStatusForm(instance=order)
    
    return render(request, 'custom_admin/orders/update.html', {
        'form': form,
        'order': order,
    })
