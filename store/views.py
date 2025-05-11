from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Avg
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth.models import User
from .models import Category, Product, Comment, Cart, CartItem, Order, ShippingAddress, UserProfile, PromoBanner, CreditCard, Notification, Voucher, OrderItem, UserVoucher, ProductRating, Package, PackageProduct, CustomizedPackage, CustomizedPackageItem, CartPackage, CartPackageItem, OrderPackage, PackageComment, PackageRating, OrderPackageItem
from .forms import CommentForm, RegisterForm, ShippingAddressForm, CreditCardForm, ProductRatingForm
from django.core.cache import cache
from django.utils import timezone
import datetime
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView, PasswordChangeView
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.utils.decorators import method_decorator
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.backends import ModelBackend
import logging
import decimal
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models import F
from django.db import transaction
from collections import defaultdict
from django.conf import settings

logger = logging.getLogger(__name__)

class ActiveUserBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if user is not None and not user.is_active:
            return None
        return user

def cleanup_duplicate_cart_packages():
    """
    Clean up duplicate CartPackage entries for the same cart and package combination.
    This is a one-time cleanup function to fix existing duplicates.
    """
    try:
        from store.models import CartPackage
        
        # Find cart-package combinations with duplicates
        duplicates = CartPackage.objects.values('cart_id', 'package_id') \
                              .annotate(count=Count('id')) \
                              .filter(count__gt=1)
        
        cleanup_count = 0
        
        # For each set of duplicates
        for duplicate in duplicates:
            with transaction.atomic():
                # Get all the matching CartPackage objects
                cart_packages = CartPackage.objects.filter(
                    cart_id=duplicate['cart_id'],
                    package_id=duplicate['package_id']
                ).order_by('created_at')
                
                # Keep the oldest one, delete the rest
                first_package = cart_packages.first()
                if first_package:
                    to_delete = cart_packages.exclude(id=first_package.id)
                    delete_count = to_delete.count()
                    to_delete.delete()
                    cleanup_count += delete_count
        
        if cleanup_count > 0:
            print(f"Cleaned up {cleanup_count} duplicate CartPackage entries.")
    except Exception as e:
        print(f"Error cleaning up duplicate CartPackage entries: {e}")

def home(request):
    featured_products = Product.objects.filter(is_active=True, is_featured=True).order_by('-created')[:8]
    featured_packages = Package.objects.filter(is_active=True, is_featured=True).order_by('-created')[:4]
    categories = Category.objects.all()
    
    # Get current active banners - using date restrictions
    today = timezone.now().date()
    # Force refresh banner cache if requested
    if 'refresh' in request.GET:
        cache.delete('homepage_banners')
    
    # Try to get banners from cache
    banners = cache.get('homepage_banners')
    if banners is None:
        date_query = (Q(start_date__isnull=True) | Q(start_date__lte=today)) & \
                    (Q(end_date__isnull=True) | Q(end_date__gte=today))
        banners = list(PromoBanner.objects.filter(active=True).filter(date_query).order_by('order')[:5])
        # Cache banners for 1 hour by default
        cache.set('homepage_banners', banners, 3600)
    
    # Add cache-busting parameters for dynamic content
    cache_bust = request.GET.get('refresh', timezone.now().timestamp())
    random_param = request.GET.get('rand', '')
    
    # If refresh parameter is provided, force fresh data and prevent caching
    response = render(request, 'store/home.html', {
        'featured_products': featured_products,
        'featured_packages': featured_packages,
        'categories': categories,
        'banners': banners,
        'cache_bust': int(float(cache_bust)),
        'random_param': random_param,
    })
    
    if 'refresh' in request.GET:
        # Add response headers to prevent browser caching
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
    
    return response

def product_list(request):
    products = Product.objects.filter(is_active=True)
    categories = Category.objects.all()
    selected_category = None
    
    # Get filter parameters
    category_slug = request.GET.get('category')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    rating = request.GET.get('rating')
    availability = request.GET.get('availability')
    sort = request.GET.get('sort', 'newest')
    
    # Apply category filter
    if category_slug:
        try:
            selected_category = Category.objects.get(slug=category_slug)
            products = products.filter(category=selected_category)
        except Category.DoesNotExist:
            pass
    
    # Apply price filters
    if min_price:
        try:
            products = products.filter(price__gte=float(min_price))
        except ValueError:
            pass
    
    if max_price:
        try:
            products = products.filter(price__lte=float(max_price))
        except ValueError:
            pass
    
    # Apply rating filter
    if rating:
        try:
            rating_value = int(rating)
            # Filter by the average_rating field that already exists on the model
            products = products.filter(average_rating__gte=rating_value)
        except ValueError:
            pass
    
    # Apply availability filter
    if availability == 'in_stock':
        products = products.filter(stock__gt=0)
    elif availability == 'out_of_stock':
        products = products.filter(stock=0)
    # If availability is not specified, show all products (both in stock and out of stock)
    
    # Apply sorting
    if sort == 'price_asc':
        products = products.order_by('price')
    elif sort == 'price_desc':
        products = products.order_by('-price')
    elif sort == 'popularity':
        products = products.annotate(
            sold_count=Count('orderitem')
        ).order_by('-sold_count')
    else:  # Default to newest
        products = products.order_by('-created')
    
    context = {
        'products': products,
        'categories': categories,
        'selected_category': selected_category,
    }
    return render(request, 'store/product_list.html', context)

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    comments = Comment.objects.filter(product=product).order_by('-created_at')
    comment_form = CommentForm()
    
    # Get product ratings
    ratings = ProductRating.objects.filter(product=product).select_related('user').order_by('-created_at')
    
    # Check if user has already rated this product
    user_has_rated = False
    user_rating = None
    if request.user.is_authenticated:
        user_rating = ProductRating.objects.filter(product=product, user=request.user).first()
        user_has_rated = user_rating is not None
        
        # Check if user has purchased this product
        user_has_purchased = OrderItem.objects.filter(
            order__user=request.user,
            product=product,
            order__status__in=['processing', 'shipped', 'delivered']
        ).exists()
    else:
        user_has_purchased = False
    
    # Initialize rating form if user hasn't rated yet
    rating_form = None
    if request.user.is_authenticated and not user_has_rated and user_has_purchased:
        rating_form = ProductRatingForm()
    
    return render(request, 'store/product_detail.html', {
        'product': product,
        'comments': comments,
        'comment_form': comment_form,
        'ratings': ratings,
        'rating_form': rating_form,
        'user_has_rated': user_has_rated,
        'user_rating': user_rating,
        'user_has_purchased': user_has_purchased,
    })

def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = Product.objects.filter(category=category, is_active=True)
    packages = Package.objects.filter(category=category, is_active=True)
    
    return render(request, 'store/category_detail.html', {
        'category': category,
        'products': products,
        'packages': packages,
    })

@login_required
def add_comment(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.product = product
            comment.user = request.user
            comment.save()
            messages.success(request, 'Your comment has been added successfully.')
        else:
            messages.error(request, 'There was an error with your comment.')
    
    return redirect('product_detail', slug=product.slug)

def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            # Create the user but set as inactive for email verification
            user = form.save(commit=False)
            user.is_active = False  # Set to inactive until email is verified
            user.save()
            
            # Create the user profile
            profile = UserProfile.objects.create(user=user)
            # Generate a verification token
            token = default_token_generator.make_token(user)
            profile.email_verification_token = token
            profile.save()
            
            # Build the verification URL
            current_site = get_current_site(request)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            verification_url = f"http://{current_site.domain}/verify-email/{uid}/{token}/"
            
            # Prepare email content
            subject = "Verify Your E-Shop Account"
            message = render_to_string('registration/verification_email.html', {
                'user': user,
                'verification_url': verification_url,
            })
            
            # Send verification email in the background
            try:
                # Use threading to send email asynchronously
                from threading import Thread
                email_thread = Thread(
                    target=send_mail,
                    args=[
                        subject,
                        message,
                        None,  # From email (will use DEFAULT_FROM_EMAIL)
                        [user.email],
                    ],
                    kwargs={
                        'fail_silently': True,
                        'html_message': message,
                    }
                )
                email_thread.start()
            except Exception as e:
                logger.error(f"Failed to send verification email: {str(e)}")
            
            # Store the user's email in session for use on verification page
            request.session['verification_email'] = user.email
            
            # Redirect to verification sent page instead of logging in
            return redirect('verification_sent')
    else:
        form = RegisterForm()
    
    return render(request, 'registration/register.html', {'form': form})

def verification_sent(request):
    # Get the email address from session if available
    email = request.session.get('verification_email', '')
    
    # Clear the session variable
    if 'verification_email' in request.session:
        del request.session['verification_email']
    
    return render(request, 'registration/verification_sent.html', {'email': email})

def verify_email(request, uidb64, token):
    try:
        # Decode the user ID
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
        
        # Get user profile
        profile = UserProfile.objects.get(user=user)
        
        # Check if the token has been used before (prevent multiple uses)
        token_cache_key = f'used_token_{token}'
        if cache.get(token_cache_key):
            messages.error(request, "This verification link has already been used.", extra_tags='danger')
            return redirect('login')
            
        # Check if there are too many attempts from this IP
        ip_address = request.META.get('REMOTE_ADDR', '')
        ip_cache_key = f'email_verify_attempts_{ip_address}'
        attempts = cache.get(ip_cache_key, 0)
        
        if attempts >= 5:  # Limit to 5 attempts per hour
            messages.error(request, "Too many verification attempts. Please try again later.", extra_tags='danger')
            return redirect('login')
        
        # Increment the attempts counter
        cache.set(ip_cache_key, attempts + 1, 3600)  # 1 hour expiry
        
        # Check if the token is valid
        if default_token_generator.check_token(user, token) and token == profile.email_verification_token:
            # Activate the user
            user.is_active = True
            user.save()
            
            # Update the profile
            profile.is_email_verified = True
            profile.email_verification_token = None  # Clear the token
            profile.save()
            
            # Mark this token as used
            cache.set(token_cache_key, True, 86400 * 30)  # Store for 30 days
            
            # Log the user in
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)
            
            messages.success(request, "Your email has been verified and your account is now active!", extra_tags='success')
            return redirect('home')
        else:
            messages.error(request, "The verification link is invalid or has expired.", extra_tags='danger')
            return redirect('login')
    except (TypeError, ValueError, OverflowError):
        messages.error(request, "Invalid verification link format. Please request a new one.", extra_tags='danger')
        return redirect('login')
    except User.DoesNotExist:
        messages.error(request, "We couldn't find a user associated with this verification link.", extra_tags='danger')
        return redirect('login')
    except UserProfile.DoesNotExist:
        messages.error(request, "User profile not found. Please contact support.", extra_tags='danger')
        return redirect('login')

def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # Get or create cart
    cart = get_or_create_cart(request)
    
    # Get quantity from form or default to 1
    quantity = int(request.POST.get('quantity', 1))
    
    # Check if product is already in cart
    try:
        cart_item = CartItem.objects.get(cart=cart, product=product)
        cart_item.quantity += quantity
        cart_item.save()
        messages.info(request, f'Updated {product.name} quantity in your cart.')
    except CartItem.DoesNotExist:
        CartItem.objects.create(cart=cart, product=product, quantity=quantity)
        messages.success(request, f'Added {product.name} to your cart.')
    
    # Redirect back to the referring page or product detail
    next_url = request.META.get('HTTP_REFERER')
    if next_url:
        return HttpResponseRedirect(next_url)
    return redirect('product_detail', slug=product.slug)

def update_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id)
    
    # Check if user has permission to modify this cart item
    if request.user.is_authenticated and cart_item.cart.user != request.user:
        messages.error(request, "You don't have permission to modify this cart.")
        return redirect('cart_detail')
    
    quantity = int(request.POST.get('quantity', 1))
    if quantity > 0:
        cart_item.quantity = quantity
        cart_item.save()
        messages.info(request, 'Cart updated successfully.')
    else:
        cart_item.delete()
        messages.info(request, 'Item removed from cart.')
    
    return redirect('cart_detail')

def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id)
    
    # Check if user has permission to modify this cart item
    if request.user.is_authenticated and cart_item.cart.user != request.user:
        messages.error(request, "You don't have permission to modify this cart.")
        return redirect('cart_detail')
    
    cart_item.delete()
    messages.info(request, 'Item removed from cart.')
    
    return redirect('cart_detail')

def cart_detail(request):
    """Display the shopping cart contents."""
    # Clean up any duplicate cart packages
    cleanup_duplicate_cart_packages()
    
    cart = get_or_create_cart(request)
    items = cart.items.all()
    packages = cart.packages.all()
    
    # Get out of stock items and package item availability
    out_of_stock_items = []
    packages_to_remove = []
    
    for item in items:
        if item.product.stock < item.quantity:
            out_of_stock_items.append(item.product.name)
    
    # Check package items availability
    package_availability = {}
    for package in packages:
        is_available = package.is_available()
        unavailable_items = package.get_unavailable_items() if not is_available else []
        
        package_availability[package.id] = {
            'available': is_available,
            'unavailable_items': unavailable_items
        }
        
        # Mark packages with unavailable items for removal
        if not is_available:
            packages_to_remove.append(package)
    
    # Remove packages with unavailable items automatically
    if packages_to_remove:
        # Create a single consolidated message for all removed packages
        removal_message = "The following packages were removed from your cart due to insufficient stock:"
        
        for package in packages_to_remove:
            unavailable_item_details = []
            for item in package.items.all():
                if item.product.stock < item.quantity:
                    unavailable_item_details.append(f"{item.product.name} (required: {item.quantity}, available: {item.product.stock})")
            
            # Add details for this package
            removal_message += f"\n\n• Package '{package.package.name}':"
            # Show top 3 unavailable items
            for i, item_detail in enumerate(unavailable_item_details[:3]):
                removal_message += f"\n  - {item_detail}"
            
            # Show a summary if there are more items
            if len(unavailable_item_details) > 3:
                removal_message += f"\n  - And {len(unavailable_item_details) - 3} more items..."
            
            # Remove the package
            package.delete()
        
        # Display a single consolidated message
        messages.warning(request, removal_message)
        
        # Refresh packages list after removal
        packages = cart.packages.all()
    
    # Group packages by package ID to handle quantities properly
    package_groups = defaultdict(list)
    for cart_package in packages:
        package_groups[cart_package.package.id].append(cart_package)
    
    # Format the grouped packages for the template
    grouped_packages = []
    for package_id, cart_packages_list in package_groups.items():
        grouped_packages.append({
            'package': cart_packages_list[0].package,
            'count': len(cart_packages_list),
            'first_cart_package': cart_packages_list[0]
        })
    
    # Create a dictionary of cart package items
    cart_package_items = {}
    for package in packages:
        cart_package_items[package.id] = package.items.all()
    
    # Get active voucher
    active_voucher = None
    if request.user.is_authenticated:
        active_voucher = cart.active_voucher
    
    # Calculate cart totals
    subtotal = cart.get_subtotal()
    voucher_discount = cart.get_voucher_discount() if active_voucher else 0
    total = subtotal - voucher_discount
    
    # Get available vouchers for the user
    available_vouchers = []
    if request.user.is_authenticated:
        available_vouchers = UserVoucher.objects.filter(
            user=request.user,
            is_used=False,
            voucher__is_active=True,
            voucher__valid_from__lte=timezone.now(),
            voucher__valid_to__gte=timezone.now(),
            voucher__min_purchase_amount__lte=subtotal
        ).select_related('voucher')
    
    return render(request, 'store/cart_detail.html', {
        'cart': cart,
        'items': items,
        'packages': packages,
        'cart_packages': packages,  # Add cart_packages for backward compatibility
        'grouped_packages': grouped_packages,
        'cart_package_items': cart_package_items,
        'package_availability': package_availability,
        'subtotal': subtotal,
        'total': total,
        'active_voucher': active_voucher,
        'voucher_discount': voucher_discount,
        'available_vouchers': available_vouchers,
        'out_of_stock_items': out_of_stock_items
    })

def remove_voucher(request):
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    elif request.session.session_key:
        cart, created = Cart.objects.get_or_create(session_id=request.session.session_key)
    else:
        return redirect('cart_detail')
    
    # Remove voucher from cart
    if cart.active_voucher:
        cart.active_voucher = None
        cart.save()
        messages.success(request, "Voucher removed successfully")
    
    return redirect('cart_detail')

# Add this new function to provide search suggestions
def search_suggestions(request):
    query = request.GET.get('query', '')
    if len(query) < 2:
        return JsonResponse([], safe=False)
    
    # Search for products matching the query in name or description
    products = Product.objects.filter(
        Q(name__icontains=query) |
        Q(description__icontains=query) |
        Q(category__name__icontains=query)
    ).filter(is_active=True)[:6]  # Limit to 6 results for performance
    
    # Search for packages matching the query in name or description
    packages = Package.objects.filter(
        Q(name__icontains=query) |
        Q(description__icontains=query) |
        Q(category__name__icontains=query)
    ).filter(is_active=True)[:3]  # Limit to 3 results
    
    # Format the response
    suggestions = []
    
    # Add products to suggestions
    for product in products:
        suggestions.append({
            'id': product.id,
            'name': product.name,
            'price': float(product.price),
            'image_url': product.image.url if product.image else None,
            'url': product.get_absolute_url(),
            'type': 'product',
            'category': product.category.name if product.category else ''
        })
    
    # Add packages to suggestions
    for package in packages:
        suggestions.append({
            'id': package.id,
            'name': package.name,
            'price': float(package.discounted_price),
            'image_url': package.image.url if package.image else None,
            'url': package.get_absolute_url(),
            'type': 'package',
            'category': package.category.name if package.category else ''
        })
    
    # Sort by relevance (exact matches first)
    sorted_suggestions = sorted(
        suggestions, 
        key=lambda x: (0 if query.lower() in x['name'].lower() else 1, 
                       0 if x['type'] == 'product' else 1)
    )
    
    return JsonResponse(sorted_suggestions, safe=False)

def search(request):
    query = request.GET.get('q', '')
    category_slug = request.GET.get('category')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    sort = request.GET.get('sort', 'relevance')
    item_type = request.GET.get('type', 'all')
    
    selected_category = None
    categories = Category.objects.all()
    
    products = Product.objects.none()
    packages = Package.objects.none()
    
    if query:
        # Get active products that match the query
        product_query = Q(name__icontains=query) | Q(description__icontains=query)
        products = Product.objects.filter(product_query, is_active=True)
        
        # Get active packages that match the query
        package_query = Q(name__icontains=query) | Q(description__icontains=query)
        packages = Package.objects.filter(package_query, is_active=True)
        
        # Filter by category if specified
        if category_slug:
            try:
                selected_category = Category.objects.get(slug=category_slug)
                products = products.filter(category=selected_category)
                # For packages, filter by products in the category
                packages = packages.filter(products__category=selected_category).distinct()
            except Category.DoesNotExist:
                pass
        
        # Apply price filters
        if min_price:
            try:
                min_price_float = float(min_price)
                products = products.filter(price__gte=min_price_float)
                packages = packages.filter(discounted_price__gte=min_price_float)
            except ValueError:
                pass
        
        if max_price:
            try:
                max_price_float = float(max_price)
                products = products.filter(price__lte=max_price_float)
                packages = packages.filter(discounted_price__lte=max_price_float)
            except ValueError:
                pass
        
        # Filter by item type
        if item_type == 'product':
            packages = Package.objects.none()
        elif item_type == 'package':
            products = Product.objects.none()
        
        # Apply sorting
        if sort == 'price_asc':
            products = products.order_by('price')
            packages = packages.order_by('discounted_price')
        elif sort == 'price_desc':
            products = products.order_by('-price')
            packages = packages.order_by('-discounted_price')
        elif sort == 'newest':
            products = products.order_by('-created')
            packages = packages.order_by('-created')
        elif sort == 'rating':
            products = products.annotate(
                avg_rating=Avg('productrating__rating')
            ).order_by('-avg_rating')
            packages = packages.annotate(
                avg_rating=Avg('packagerating__rating')
            ).order_by('-avg_rating')
        # For 'relevance' (default), we keep the order based on the search query match
    
    total_count = products.count() + packages.count()
    
    context = {
        'query': query,
        'products': products,
        'packages': packages,
        'total_count': total_count,
        'categories': categories,
        'selected_category': selected_category,
        'min_price': min_price,
        'max_price': max_price,
        'sort': sort,
        'item_type': item_type,
    }
    
    return render(request, 'store/search_results.html', context)

@login_required
def profile(request):
    # Check if the request is from a mobile device
    is_mobile = False
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    mobile_keywords = ['mobile', 'android', 'iphone', 'ipad', 'ipod']
    
    if any(keyword in user_agent for keyword in mobile_keywords):
        is_mobile = True
    
    # Get loyalty information
    from custom_admin.models import CustomerLoyalty, LoyaltyTier
    loyalty, created = CustomerLoyalty.objects.get_or_create(user=request.user)
    
    # Calculate next tier if applicable
    next_tier = None
    if loyalty.current_tier:
        next_tier = LoyaltyTier.objects.filter(
            minimum_spend__gt=loyalty.current_tier.minimum_spend
        ).order_by('minimum_spend').first()
    else:
        next_tier = LoyaltyTier.objects.all().order_by('minimum_spend').first()
    
    # Calculate progress to next tier
    progress_percentage = 0
    amount_to_next_tier = 0
    
    if next_tier:
        current_minimum = 0
        if loyalty.current_tier:
            current_minimum = loyalty.current_tier.minimum_spend
            
        tier_range = next_tier.minimum_spend - current_minimum
        progress = loyalty.total_spend - current_minimum
        
        if tier_range > 0:
            # Convert Decimal to float before division
            progress_percentage = min(100, int((float(progress) / float(tier_range)) * 100))
            amount_to_next_tier = next_tier.minimum_spend - loyalty.total_spend
    
    # For mobile devices, use the mobile-specific template
    if is_mobile or request.GET.get('mobile_view', False):
        # Get sort parameter from request
        sort_by = request.GET.get('sort', '-created_at')
        
        # Get orders with pagination
        orders = Order.objects.filter(user=request.user).order_by(sort_by)
        paginator = Paginator(orders, 5)  # Show 5 orders per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Get user's addresses 
        addresses = ShippingAddress.objects.filter(user=request.user)
        
        # Get only valid vouchers for mobile view
        now = timezone.now()
        user_vouchers = UserVoucher.objects.filter(
            user=request.user,
            is_used=False,
            voucher__is_active=True,
            voucher__valid_from__lte=now,
            voucher__valid_to__gte=now
        ).select_related('voucher')
        
        # Get loyalty vouchers
        from custom_admin.models import LoyaltyVoucher
        loyalty_vouchers = LoyaltyVoucher.objects.filter(
            user=request.user,
            is_used=False,
            valid_until__gte=timezone.now()
        ).order_by('-created_at')
        
        context = {
            'page_obj': page_obj,
            'addresses': addresses,
            'user_vouchers': user_vouchers,
            'sort_by': sort_by,
            'loyalty': loyalty,
            'next_tier': next_tier,
            'progress_percentage': progress_percentage,
            'amount_to_next_tier': amount_to_next_tier,
            'loyalty_vouchers': loyalty_vouchers,
        }
        return render(request, 'store/mobile_account.html', context)
    else:
        # Original desktop version
        # Get sort parameter from request
        sort_by = request.GET.get('sort', '-created_at')
        
        # Validate sort parameter
        valid_sort_fields = ['created_at', '-created_at', 'id', '-id']
        if sort_by not in valid_sort_fields:
            sort_by = '-created_at'
        
        # Get orders with pagination
        orders = Order.objects.filter(user=request.user).order_by(sort_by)
        paginator = Paginator(orders, 5)  # Show 5 orders per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Get user's addresses and comments
        addresses = ShippingAddress.objects.filter(user=request.user)
        comments = Comment.objects.filter(user=request.user)
        
        # Get loyalty vouchers
        from custom_admin.models import LoyaltyVoucher
        loyalty_vouchers = LoyaltyVoucher.objects.filter(
            user=request.user,
            is_used=False,
            valid_until__gte=timezone.now()
        ).order_by('-created_at')
        
        context = {
            'page_obj': page_obj,
            'addresses': addresses,
            'comments': comments,
            'sort_by': sort_by,
            'loyalty': loyalty,
            'next_tier': next_tier,
            'progress_percentage': progress_percentage,
            'amount_to_next_tier': amount_to_next_tier,
            'loyalty_vouchers': loyalty_vouchers,
        }
        return render(request, 'store/profile.html', context)

@login_required
def add_address(request):
    if request.method == 'POST':
        form = ShippingAddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            
            # If this is the first address, set it as default
            if not ShippingAddress.objects.filter(user=request.user, is_default=True).exists():
                address.is_default = True
                address.save()
            
            messages.success(request, 'Address added successfully!')
            return redirect('profile')
    else:
        form = ShippingAddressForm()
    
    return render(request, 'store/add_address.html', {'form': form})

@login_required
def edit_address(request, address_id):
    address = get_object_or_404(ShippingAddress, id=address_id, user=request.user)
    
    if request.method == 'POST':
        form = ShippingAddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, 'Address updated successfully!')
            return redirect('profile')
    else:
        form = ShippingAddressForm(instance=address)
    
    return render(request, 'store/edit_address.html', {'form': form, 'address': address})

@login_required
def delete_address(request, address_id):
    address = get_object_or_404(ShippingAddress, id=address_id, user=request.user)
    
    if request.method == 'POST':
        address.delete()
        messages.success(request, 'Address deleted successfully!')
        return redirect('profile')
    
    return render(request, 'store/delete_address.html', {'address': address})

@login_required
def set_default_address(request, address_id):
    address = get_object_or_404(ShippingAddress, id=address_id, user=request.user)
    
    # Remove default status from all other addresses
    ShippingAddress.objects.filter(user=request.user).update(is_default=False)
    
    # Set the selected address as default
    address.is_default = True
    address.save()
    
    messages.success(request, 'Default address updated successfully.')
    return redirect('profile')

@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if order.status == 'pending':
        order.status = 'cancelled'
        order.save()
        messages.success(request, 'Order cancelled successfully!')
    else:
        messages.error(request, 'This order cannot be cancelled.')
    
    return redirect('profile')

# Custom Password Reset Views with rate limiting
class CustomPasswordResetView(PasswordResetView):
    template_name = 'registration/password_reset_form.html'
    email_template_name = 'registration/password_reset_email.txt'
    html_email_template_name = 'registration/password_reset_email.html'
    subject_template_name = 'registration/password_reset_subject.txt'
    success_url = '/password-reset/done/'
    
    def dispatch(self, request, *args, **kwargs):
        # Check rate limiting for IP address
        ip_address = request.META.get('REMOTE_ADDR', '')
        cache_key = f'password_reset_attempts_{ip_address}'
        attempts = cache.get(cache_key, 0)
        
        # Limit to 3 password reset requests per hour per IP
        if attempts >= 3 and request.method == 'POST':
            messages.error(request, "Too many password reset attempts. Please try again later.")
            return redirect('login')
        
        # If it's a POST request, increment the counter
        if request.method == 'POST':
            cache.set(cache_key, attempts + 1, 3600)  # 1 hour expiry
            
        return super().dispatch(request, *args, **kwargs)

@method_decorator([never_cache, csrf_protect, sensitive_post_parameters()], name='dispatch')
class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'registration/password_reset_confirm.html'
    success_url = '/password-reset-complete/'
    
    def dispatch(self, request, *args, **kwargs):
        # Check token usage
        token = kwargs.get('token')
        if token:
            token_cache_key = f'used_password_reset_token_{token}'
            if cache.get(token_cache_key):
                messages.error(request, "This password reset link has already been used.")
                return redirect('password_reset')
                
        # Check rate limiting for IP address
        ip_address = request.META.get('REMOTE_ADDR', '')
        cache_key = f'password_reset_confirm_attempts_{ip_address}'
        attempts = cache.get(cache_key, 0)
        
        # Limit to 5 attempts per hour per IP
        if attempts >= 5:
            messages.error(request, "Too many password reset attempts. Please try again later.")
            return redirect('login')
            
        # Increment the counter
        cache.set(cache_key, attempts + 1, 3600)  # 1 hour expiry
        
        response = super().dispatch(request, *args, **kwargs)
        
        # If POST and form is valid, mark token as used
        if request.method == 'POST' and hasattr(self, 'form') and self.form.is_valid():
            if token:
                cache.set(token_cache_key, True, 86400 * 30)  # Store for 30 days
                
        # Auto-redirect to success page if token is valid
        if self.validlink and request.method == 'GET':
            return redirect(self.get_success_url())
            
        return response

@login_required
def order_bill(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'store/order_bill.html', {'order': order})

def social_auth_error(request):
    error_message = request.GET.get('message', 'An error occurred during social authentication.')
    error_code = request.GET.get('error', None)
    
    # Specific handling for disallowed_useragent error
    if error_code == 'disallowed_useragent' or 'disallowed_useragent' in error_message.lower():
        error_message = """Google has blocked this sign-in attempt because your browser doesn't meet their security requirements.
        
        Try one of these solutions:
        1. Use a desktop browser like Chrome, Firefox, or Edge
        2. Open the site in your mobile browser's "Desktop mode"
        3. Use email registration instead
        
        Error details: Google OAuth disallowed_useragent - Your browser was detected as insecure for OAuth authentication."""
    
    return render(request, 'registration/social_auth_error.html', {
        'error_message': error_message,
        'error_code': error_code
    })

def terms_and_conditions(request):
    return render(request, 'terms_and_conditions.html')

def faq(request):
    from custom_admin.models import FAQ
    faqs = FAQ.objects.filter(is_published=True).order_by('order', 'title')
    return render(request, 'faq.html', {'faqs': faqs})

def notifications(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    # Auto cleanup old notifications
    Notification.delete_old_read_notifications()
    
    # Get all notifications for the user
    notifications_list = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Set up pagination
    paginator = Paginator(notifications_list, 10)  # 10 notifications per page
    page = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    
    return render(request, 'store/notifications.html', {
        'page_obj': page_obj,
        'unread_count': notifications_list.filter(is_read=False).count()
    })

@login_required
def delete_notification(request, notification_id):
    """Permanently delete a notification."""
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.delete()
        messages.success(request, "Notification deleted successfully.")
    except Notification.DoesNotExist:
        messages.error(request, "Notification not found.")
    
    return redirect('notifications')

@login_required
def mark_notification_read(request, notification_id):
    """Mark a specific notification as read."""
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()
        messages.success(request, "Notification marked as read.")
    except Notification.DoesNotExist:
        messages.error(request, "Notification not found.")
    
    # Check if there's a next parameter to redirect back to original page
    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('notifications')

@login_required
def mark_all_notifications_read(request):
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Get all unread notifications for the user
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def add_credit_card(request):
    if request.method == 'POST':
        form = CreditCardForm(request.POST)
        if form.is_valid():
            credit_card = form.save(commit=False)
            credit_card.user = request.user
            credit_card.save()
            
            messages.success(request, 'Credit card added successfully!')
            return redirect('profile')
    else:
        form = CreditCardForm()
    
    return render(request, 'store/add_credit_card.html', {'form': form})

@login_required
def my_vouchers(request):
    user = request.user
    # Get regular store vouchers
    user_vouchers = UserVoucher.objects.filter(
        user=user,
        voucher__is_active=True  # Only show active vouchers
    ).select_related('voucher')
    
    vouchers_data = []
    for user_voucher in user_vouchers:
        voucher = user_voucher.voucher
        # Skip inactive dedicated vouchers
        if voucher.voucher_type == 'dedicated' and not voucher.is_active:
            continue
            
        voucher_data = {
            'id': voucher.id,
            'name': voucher.code,
            'code': voucher.code,
            'discount_amount': voucher.discount_value,
            'discount_type': voucher.get_discount_type_display(),
            'min_purchase': voucher.min_purchase_amount,
            'expiry_date': voucher.valid_to,
            'remaining_qty': voucher.usage_limit - voucher.used_count if voucher.usage_limit else 'Unlimited',
            'is_dedicated': voucher.voucher_type == 'dedicated',
            'active': voucher.is_active,
            'description': f"Save {voucher.discount_value}{'%' if voucher.discount_type == 'percentage' else '$'} on your purchase",
            'voucher_type': 'regular',
        }
        vouchers_data.append(voucher_data)
    
    # Get loyalty vouchers
    try:
        from custom_admin.models import LoyaltyVoucher
        now = timezone.now()
        loyalty_vouchers = LoyaltyVoucher.objects.filter(
            user=user,
            is_used=False,
            valid_until__gte=now
        ).select_related('tier')
        
        for loyalty_voucher in loyalty_vouchers:
            voucher_type_display = "Anniversary Voucher" if loyalty_voucher.voucher_type == 'anniversary' else f"Loyalty Tier Voucher"
            tier_name = loyalty_voucher.tier.name if loyalty_voucher.tier else ""
            
            voucher_data = {
                'id': loyalty_voucher.id,
                'name': f"{voucher_type_display}" + (f" - {tier_name}" if tier_name else ""),
                'code': loyalty_voucher.code,
                'discount_amount': loyalty_voucher.amount,
                'discount_type': 'Fixed Amount',
                'min_purchase': 0,
                'expiry_date': loyalty_voucher.valid_until,
                'remaining_qty': 1,
                'is_dedicated': True,
                'active': True,
                'description': f"${loyalty_voucher.amount} off your purchase as a loyalty reward",
                'voucher_type': 'loyalty',
            }
            vouchers_data.append(voucher_data)
    except Exception as e:
        # Log but continue if there's an issue with loyalty vouchers
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error retrieving loyalty vouchers: {str(e)}")
    
    # Sort vouchers by expiry date (soonest first)
    vouchers_data.sort(key=lambda x: x['expiry_date'])
    
    context = {
        'vouchers': vouchers_data,
        'active_tab': 'my_vouchers'
    }
    return render(request, 'store/my_vouchers.html', context)

@login_required
def checkout(request):
    """Handle the checkout process."""
    logger.info(f"[CHECKOUT] User {request.user.id} starting checkout. Method: {request.method}")
    print("\n===== CHECKOUT DEBUG =====")
    print(f"Request method: {request.method}")
    print(f"GET params: {request.GET}")

    if request.method == 'POST':
        print(f"POST params: {request.POST}")

    try:
        cart = Cart.objects.get(user=request.user)
        logger.info(f"[CHECKOUT] Cart {cart.id} found for user {request.user.id}. Items: {cart.items.count()}, Packages: {cart.packages.count()}, Active Voucher: {cart.active_voucher}")
        print(f"Cart found: {cart.id}")
        print(f"Cart items count: {cart.items.count()}")
        print(f"Cart packages count: {cart.packages.count()}")

        if cart.items.count() == 0 and cart.packages.count() == 0:
            logger.warning(f"[CHECKOUT] Cart {cart.id} is empty. Redirecting to cart_detail.")
            print("Cart is empty - redirecting")
            messages.warning(request, "Your cart is empty.")
            return redirect('cart_detail')
    except Cart.DoesNotExist:
        logger.error(f"[CHECKOUT] No cart found for user {request.user.id}. Redirecting to cart_detail.")
        print("No cart found - redirecting")
        messages.warning(request, "Your cart is empty.")
        return redirect('cart_detail')
    
    # Get selected items from the query parameters for GET or form data for POST
    if request.method == 'GET':
        selected_item_ids = request.GET.getlist('selected_items', [])
        selected_package_ids = request.GET.getlist('selected_packages', [])
    else:  # POST request
        selected_item_ids = request.POST.getlist('selected_items', [])
        selected_package_ids = request.POST.getlist('selected_packages', [])
    
    print(f"Selected item IDs: {selected_item_ids}")
    print(f"Selected package IDs: {selected_package_ids}")
    
    if not selected_item_ids and not selected_package_ids:
        print("No items/packages selected - redirecting")
        messages.warning(request, "Please select at least one item to checkout.")
        return redirect('cart_detail')
    
    # Get only the selected cart items
    selected_items = cart.items.filter(id__in=selected_item_ids)
    selected_packages = cart.packages.filter(id__in=selected_package_ids)
    
    print(f"Found selected items: {selected_items.count()}")
    print(f"Found selected packages: {selected_packages.count()}")
    
    if not selected_items.exists() and not selected_packages.exists():
        print("Selected items/packages not found in cart - redirecting")
        messages.warning(request, "Selected items not found in your cart.")
        return redirect('cart_detail')
    
    # Check if any selected items are out of stock
    out_of_stock_items = []
    for item in selected_items:
        if item.product.stock < item.quantity:
            out_of_stock_items.append(item.product.name)
    
    # Check if any package items are out of stock
    for package in selected_packages:
        if not package.is_available():
            unavailable = package.get_unavailable_items()
            out_of_stock_items.append(f"Package '{package.package.name}' contains unavailable items: {', '.join(unavailable)}")
    
    if out_of_stock_items:
        messages.error(request, f"Some items are out of stock: {', '.join(out_of_stock_items)}. Please remove them from your selection.")
        return redirect('cart_detail')
    
    # Process the checkout form
    if request.method == 'POST':
        # Get form data
        shipping_address_id = request.POST.get('shipping_address')
        payment_method = request.POST.get('payment_method')
        phone_number = request.POST.get('phone_number')
        order_notes = request.POST.get('order_notes')
        
        # Validate required fields
        if not shipping_address_id:
            messages.error(request, "Please select a shipping address.")
            return redirect('checkout')
        
        if not payment_method:
            messages.error(request, "Please select a payment method.")
            return redirect('checkout')
        
        # Get the shipping address
        try:
            shipping_address = ShippingAddress.objects.get(id=shipping_address_id, user=request.user)
        except ShippingAddress.DoesNotExist:
            messages.error(request, "Invalid shipping address selected.")
            return redirect('checkout')
        
        # Calculate order totals for selected items and packages
        subtotal = sum(item.product.price * item.quantity for item in selected_items)
        subtotal += sum(package.total_price for package in selected_packages)
        
        shipping_fee = decimal.Decimal('10.00')
        
        # Apply voucher discount if available
        user_voucher = cart.active_voucher
        voucher_discount = 0
        if user_voucher and user_voucher.is_valid:
            voucher_discount = user_voucher.voucher.calculate_discount(subtotal)
            logger.info(f"[CHECKOUT] Applying UserVoucher {user_voucher.id} (Voucher {user_voucher.voucher.id}) to order. Discount: {voucher_discount}")
        else:
            user_voucher = None
            logger.info(f"[CHECKOUT] No valid voucher applied to order.")
        
        total_price = subtotal + shipping_fee - voucher_discount
        
        # Create the order
        try:
            order = Order.objects.create(
                user=request.user,
                shipping_address=shipping_address,
                phone_number=phone_number or shipping_address.phone_number,
                order_notes=order_notes,
                payment_method=payment_method,
                subtotal=subtotal,
                shipping_fee=shipping_fee,
                voucher=user_voucher,
                voucher_discount=voucher_discount,
                total_price=total_price,
                status='pending'
            )
            logger.info(f"[CHECKOUT] Created Order {order.id} for user {request.user.id} with UserVoucher {order.voucher.id if order.voucher else 'None'}.")
        except Exception as e:
            logger.error(f"[CHECKOUT] Error creating order for user {request.user.id}: {e}")
            messages.error(request, "An error occurred while creating your order. Please try again.")
            return redirect('checkout')
        
        # Add selected cart items to order
        for cart_item in selected_items:
            # Double check stock again before creating order item
            if cart_item.product.stock >= cart_item.quantity:
                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    quantity=cart_item.quantity,
                    price=cart_item.product.price
                )
                
                # Update stock quantity
                cart_item.product.stock -= cart_item.quantity
                cart_item.product.save()
            else:
                # If something became out of stock during checkout, handle it
                order.delete()
                messages.error(request, f"{cart_item.product.name} is now out of stock.")
                return redirect('cart_detail')
        
        # Add selected packages to order
        for cart_package in selected_packages:
            # Double check all package items stock before creating order package
            if cart_package.is_available():
                order_package = OrderPackage.objects.create(
                    order=order,
                    package=cart_package.package,
                    price=cart_package.total_price
                )
                
                # Add package items to order
                for package_item in cart_package.items.all():
                    OrderPackageItem.objects.create(
                        order_package=order_package,
                        product=package_item.product,
                        quantity=package_item.quantity,
                        price=package_item.product.price
                    )
                    
                    # Update stock quantity for package items
                    package_item.product.stock -= package_item.quantity
                    package_item.product.save()
            else:
                # If something became out of stock during checkout, handle it
                order.delete()
                unavailable = cart_package.get_unavailable_items()
                messages.error(request, f"Some items in package '{cart_package.package.name}' are now out of stock: {', '.join(unavailable)}")
                return redirect('cart_detail')
        
        # Comment out or remove the line that marks the voucher as used
        # if order.voucher:
        #     order.voucher.use_voucher() 
            
        # Remove the selected items from cart
        selected_items.delete()
        selected_packages.delete()
        
        # If cart is empty after removing selected items, remove voucher
        if cart.items.count() == 0 and cart.packages.count() == 0:
            logger.info(f"[CHECKOUT] Cart {cart.id} is now empty. Removing active voucher {cart.active_voucher.id if cart.active_voucher else 'None'} from cart.")
            cart.active_voucher = None
            cart.save()
        
        # Create a notification for the user
        Notification.objects.create(
            user=request.user,
            title="Order Placed",
            message=f"Your order #{order.id} has been placed successfully.",
            notification_type="order",
            reference_id=order.id,
            link=reverse('order_detail', kwargs={'order_id': order.id})
        )
        
        # Redirect to payment page
        logger.info(f"[CHECKOUT] Redirecting user {request.user.id} to payment for order {order.id}.")
        return redirect('payment', order_id=order.id)
    
    # For GET requests, prepare the checkout page with selected items
    # Get user's addresses and payment methods
    shipping_addresses = ShippingAddress.objects.filter(user=request.user)
    credit_cards = CreditCard.objects.filter(user=request.user)
    
    # Check if user has a default address
    default_address = shipping_addresses.filter(is_default=True).first()
    
    # Calculate subtotal for selected items only
    selected_subtotal = sum(item.product.price * item.quantity for item in selected_items)
    selected_subtotal += sum(package.total_price for package in selected_packages)
    
    # Prepare shipping addresses JSON for JavaScript
    import json
    shipping_addresses_data = []
    for address in shipping_addresses:
        shipping_addresses_data.append({
            'id': address.id,
            'name': address.name,
            'phone': address.phone_number or 'N/A',
            'address1': address.address_line1,
            'address2': address.address_line2 or '',
            'city': address.city,
            'state': address.state,
            'postalCode': address.postal_code,
            'country': address.country
        })
    shipping_addresses_json = json.dumps(shipping_addresses_data)
    
    return render(request, 'store/checkout.html', {
        'cart': cart,
        'selected_items': selected_items,
        'selected_packages': selected_packages,
        'selected_subtotal': selected_subtotal,
        'shipping_addresses': shipping_addresses,
        'shipping_addresses_json': shipping_addresses_json,
        'default_address': default_address,
        'credit_cards': credit_cards,
    })

@login_required
def payment(request, order_id):
    """Handle payment for an order."""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    # Check if order is already paid
    if order.payment_status:
        messages.info(request, "This order has already been paid.")
        return redirect('order_detail', order_id=order.id)
    
    # Get user's saved credit cards
    credit_cards = CreditCard.objects.filter(user=request.user)
    selected_card = None
    
    if request.method == 'POST':
        # Process payment
        card_id = request.POST.get('card_id')
        
        # If using saved card
        if card_id:
            try:
                selected_card = CreditCard.objects.get(id=card_id, user=request.user)
            except CreditCard.DoesNotExist:
                messages.error(request, "Invalid card selected.")
                return redirect('payment', order_id=order.id)
        else:
            # Process new card details
            card_number = request.POST.get('card_number')
            card_holder = request.POST.get('card_holder')
            expiry_month = request.POST.get('expiry_month')
            expiry_year = request.POST.get('expiry_year')
            cvv = request.POST.get('cvv')
            save_card = request.POST.get('save_card')
            
            # Basic validation
            if not all([card_number, card_holder, expiry_month, expiry_year, cvv]):
                messages.error(request, "Please fill in all card details.")
                return redirect('payment', order_id=order.id)
            
            # Format card number for display (masked)
            masked_number = f"**** **** **** {card_number[-4:]}"
            
            # Save card if requested
            if save_card:
                new_card = CreditCard.objects.create(
                    user=request.user,
                    card_holder=card_holder,
                    masked_number=masked_number,
                    expiry_month=expiry_month,
                    expiry_year=expiry_year
                )
                selected_card = new_card
        
        # In a real application, you would integrate with a payment gateway here
        # For now, we'll just mark the order as paid
        order.payment_status = True
        order.status = 'processing'
        order.save()
        
        # Update product sold_count for each item in the order
        for order_item in order.items.all():
            product = order_item.product
            product.sold_count = F('sold_count') + order_item.quantity
            product.save(update_fields=['sold_count'])
        
        # Create a notification for the user
        Notification.objects.create(
            user=request.user,
            title="Payment Successful",
            message=f"Your payment for order #{order.id} was successful.",
            notification_type="payment",
            reference_id=order.id,
            link=reverse('order_detail', kwargs={'order_id': order.id})
        )
        
        # Send order confirmation email
        try:
            subject = f"Your E-Shop Order Confirmation #{order.order_number}"
            # Basic text email body (replace with render_to_string for HTML later)
            # NOTE: Create store/email/order_confirmation_email.html for a proper HTML email
            context = {
                'order': order,
                'domain': request.get_host(), # Get current domain
                'protocol': 'https' if request.is_secure() else 'http'
            }
            # html_message = render_to_string('store/email/order_confirmation_email.html', context)
            # For now, using a simple text message
            message = f"Hi {order.user.first_name or order.user.username},\n\n"
            message += f"Thank you for your order! Your order number is {order.order_number}.\n"
            message += f"Total Amount: ${order.total_price:.2f}\n"
            message += f"You can view your order details here: {context['protocol']}://{context['domain']}{reverse('order_detail', args=[order.id])}\n\n"
            message += "Thanks for shopping with E-Shop!"

            send_mail(
                subject,
                message, # Use plain text message for now
                settings.DEFAULT_FROM_EMAIL,
                [order.user.email],
                # html_message=html_message, # Uncomment this when HTML template is ready
                fail_silently=False,
            )
            logger.info(f"Order confirmation email sent successfully for order {order.id} to {order.user.email}")
        except Exception as e:
            logger.error(f"Failed to send order confirmation email for order {order.id}: {e}")
            # Optionally inform the user or retry later, but don't block the success redirect
        
        messages.success(request, "Payment successful! Your order is being processed.")
        return redirect('order_success', order_id=order.id)
    
    return render(request, 'store/payment.html', {
        'order': order,
        'credit_cards': credit_cards,
        'credit_card': selected_card
    })

@login_required
def complete_payment(request, order_id):
    """Process the payment and complete the order."""
    logger.info(f"[PAYMENT_COMPLETE] Starting completion for Order {order_id}, User {request.user.id}")
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    # Mark order as paid and update status
    order.payment_status = True
    order.status = 'processing'
    order.save()
    logger.info(f"[PAYMENT_COMPLETE] Order {order.id} marked as paid and processing.")
    
    # Update product sold_count for each item in the order
    for order_item in order.items.all():
        product = order_item.product
        product.sold_count = F('sold_count') + order_item.quantity
        product.save(update_fields=['sold_count'])
    
    # Mark voucher as used *after* successful payment
    if order.voucher:
        try:
            order.voucher.use_voucher()
            logger.info(f"Successfully marked voucher {order.voucher.voucher.code} as used for order {order.id}")
        except Exception as e:
            logger.error(f"Error marking voucher {order.voucher.voucher.code} as used for order {order.id}: {e}")
            # Decide if you want to fail the order or just log the error

    # Update loyalty status and create loyalty vouchers if applicable
    try:
        from custom_admin.services.loyalty_service import update_customer_loyalty
        tier_changed, voucher_created, new_tier = update_customer_loyalty(request.user, order.total_price)
        
        # Notify user about loyalty changes
        if tier_changed and new_tier:
            Notification.objects.create(
                user=request.user,
                title=f"Upgraded to {new_tier.name} Tier!",
                message=f"Congratulations! You've been upgraded to {new_tier.name} loyalty tier. Enjoy your new benefits!",
                notification_type="loyalty",
                link=reverse('profile')
            )
            
            if voucher_created:
                Notification.objects.create(
                    user=request.user,
                    title="New Loyalty Voucher",
                    message=f"You've received a new voucher for reaching the {new_tier.name} tier. Check your vouchers section!",
                    notification_type="voucher",
                    link=reverse('my_vouchers')
                )
    except Exception as e:
        # Log error but don't stop the order process
        logger.error(f"Error updating loyalty for order {order.id}: {e}")
    
    # Create a notification for the user
    Notification.objects.create(
        user=request.user,
        title="Payment Successful",
        message=f"Your payment for order #{order.id} was successful.",
        notification_type="payment",
        reference_id=order.id,
        link=reverse('order_detail', kwargs={'order_id': order.id})
    )
    
    # Send order confirmation email
    try:
        subject = f"Your E-Shop Order Confirmation #{order.order_number}"
        # Basic text email body (replace with render_to_string for HTML later)
        # NOTE: Create store/email/order_confirmation_email.html for a proper HTML email
        context = {
            'order': order,
            'domain': request.get_host(), # Get current domain
            'protocol': 'https' if request.is_secure() else 'http'
        }
        # html_message = render_to_string('store/email/order_confirmation_email.html', context)
        # For now, using a simple text message
        message = f"Hi {order.user.first_name or order.user.username},\n\n"
        message += f"Thank you for your order! Your order number is {order.order_number}.\n"
        message += f"Total Amount: ${order.total_price:.2f}\n"
        message += f"You can view your order details here: {context['protocol']}://{context['domain']}{reverse('order_detail', args=[order.id])}\n\n"
        message += "Thanks for shopping with E-Shop!"

        send_mail(
            subject,
            message, # Use plain text message for now
            settings.DEFAULT_FROM_EMAIL,
            [order.user.email],
            # html_message=html_message, # Uncomment this when HTML template is ready
            fail_silently=False,
        )
        logger.info(f"Order confirmation email sent successfully for order {order.id} to {order.user.email}")
    except Exception as e:
        logger.error(f"Failed to send order confirmation email for order {order.id}: {e}")
        # Optionally inform the user or retry later, but don't block the success redirect
    
    messages.success(request, "Payment successful! Your order is being processed.")
    return redirect('order_success', order_id=order.id)

@login_required
def order_success(request, order_id):
    """Display order success page."""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'store/order_success.html', {'order': order})

@login_required
def order_detail(request, order_id):
    """Display order details."""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'store/order_detail.html', {'order': order})

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if not user.is_active:
                messages.error(request, "Your account is inactive. Please contact support.")
                return render(request, 'registration/login.html')
            
            login(request, user)
            
            # Check if there's a next parameter to redirect to
            next_url = request.GET.get('next', 'home')
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password.")
    
    return render(request, 'registration/login.html')

def get_or_create_cart(request):
    """Helper function to get or create a cart for the current user or session"""
    if request.user.is_authenticated:
        # Try to get an existing cart for this user
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        # For anonymous users, use session ID
        session_id = request.session.session_key
        if not session_id:
            # Create a new session if one doesn't exist
            request.session.save()
            session_id = request.session.session_key
        
        # Try to get an existing cart for this session
        cart, created = Cart.objects.get_or_create(session_id=session_id)
    
    return cart

@login_required
def add_voucher_to_cart(request):
    if request.method == 'POST':
        voucher_code = request.POST.get('voucher_code')
        if not voucher_code:
            messages.error(request, "Please enter a voucher code.")
            return redirect('cart_detail')

        cart = get_or_create_cart(request)
        logger.info(f"[VOUCHER_ADD] User {request.user.id} attempting to add voucher code: '{voucher_code}' to cart {cart.id}")

        # First, try to find any voucher with this code (regardless of type)
        try:
            # Look for the voucher itself first
            voucher = Voucher.objects.get(code__iexact=voucher_code)
            logger.info(f"[VOUCHER_ADD] Found Voucher {voucher.id} (Type: {voucher.voucher_type}, Active: {voucher.is_active}, Used: {voucher.used_count}/{voucher.usage_limit})")

            # Check if voucher is active
            if not voucher.is_active:
                logger.warning(f"[VOUCHER_ADD] FAILED: Voucher {voucher.id} is not active.")
                messages.error(request, f"Voucher '{voucher_code}' is not active.")
                cart.active_voucher = None
                cart.save()
                return redirect('cart_detail')

            # Check time validity
            now = timezone.now()
            if not (voucher.valid_from <= now <= voucher.valid_to):
                logger.warning(f"[VOUCHER_ADD] FAILED: Voucher {voucher.id} validity period check failed (Valid: {voucher.valid_from} - {voucher.valid_to}, Now: {now}).")
                if now < voucher.valid_from:
                    messages.error(request, f"Voucher '{voucher_code}' is not valid yet. It will be active from {voucher.valid_from.strftime('%Y-%m-%d')}.")
                else:
                    messages.error(request, f"Voucher '{voucher_code}' has expired on {voucher.valid_to.strftime('%Y-%m-%d')}.")
                cart.active_voucher = None
                cart.save()
                return redirect('cart_detail')

            # Check usage limit (on the main Voucher object)
            if voucher.used_count >= voucher.usage_limit:
                logger.warning(f"[VOUCHER_ADD] FAILED: Voucher {voucher.id} usage limit reached ({voucher.used_count}/{voucher.usage_limit}).")
                messages.error(request, f"Voucher '{voucher_code}' has reached its usage limit.")
                cart.active_voucher = None
                cart.save()
                return redirect('cart_detail')

            # Check minimum purchase amount against cart subtotal
            subtotal = cart.get_subtotal()
            if subtotal < voucher.min_purchase_amount:
                logger.warning(f"[VOUCHER_ADD] FAILED: Voucher {voucher.id} minimum purchase not met (Subtotal: {subtotal}, Min: {voucher.min_purchase_amount}).")
                messages.error(request, f"Minimum purchase of ${voucher.min_purchase_amount} required for this voucher. Your current subtotal is ${subtotal}.")
                cart.active_voucher = None
                cart.save()
                return redirect('cart_detail')

            # Handle differently based on voucher type
            if voucher.voucher_type == 'dedicated':
                logger.info(f"[VOUCHER_ADD] Handling dedicated voucher {voucher.id}")
                # For dedicated vouchers, must have a specific user assignment
                try:
                    user_voucher = UserVoucher.objects.get(user=request.user, voucher=voucher)
                    logger.info(f"[VOUCHER_ADD] Found dedicated UserVoucher {user_voucher.id} (Used: {user_voucher.is_used})")
                    if user_voucher.is_used:
                        logger.warning(f"[VOUCHER_ADD] FAILED: Dedicated UserVoucher {user_voucher.id} already used.")
                        messages.error(request, f"You have already used voucher '{voucher_code}'.")
                        cart.active_voucher = None
                        cart.save()
                    else:
                        cart.active_voucher = user_voucher
                        cart.save()
                        logger.info(f"[VOUCHER_ADD] SUCCESS: Applied dedicated UserVoucher {user_voucher.id} to cart {cart.id}")
                        messages.success(request, f"Voucher '{voucher_code}' applied successfully.")
                except UserVoucher.DoesNotExist:
                    logger.warning(f"[VOUCHER_ADD] FAILED: Dedicated UserVoucher not found for user {request.user.id} and voucher {voucher.id}.")
                    messages.error(request, f"Voucher '{voucher_code}' is not assigned to your account.")
                    cart.active_voucher = None
                    cart.save()
            else: # General voucher
                logger.info(f"[VOUCHER_ADD] Handling general voucher {voucher.id}")
                # For general vouchers, create/get user assignment
                user_voucher, created = UserVoucher.objects.get_or_create(
                    user=request.user,
                    voucher=voucher,
                    defaults={'is_used': False}
                )
                if created:
                    logger.info(f"[VOUCHER_ADD] Created new UserVoucher {user_voucher.id} for general voucher {voucher.id}")
                else:
                    logger.info(f"[VOUCHER_ADD] Found existing UserVoucher {user_voucher.id} (Used: {user_voucher.is_used}) for general voucher {voucher.id}")

                if user_voucher.is_used:
                    logger.warning(f"[VOUCHER_ADD] FAILED: General UserVoucher {user_voucher.id} already used.")
                    messages.error(request, f"You have already used voucher '{voucher_code}'.")
                    cart.active_voucher = None
                    cart.save()
                else:
                    # Check general voucher's main usage limit again (edge case)
                    if voucher.used_count >= voucher.usage_limit:
                         logger.warning(f"[VOUCHER_ADD] FAILED: General Voucher {voucher.id} usage limit reached ({voucher.used_count}/{voucher.usage_limit}) just before applying.")
                         messages.error(request, f"Voucher '{voucher_code}' has reached its usage limit.")
                         cart.active_voucher = None
                         cart.save()
                    else:
                        cart.active_voucher = user_voucher
                        cart.save()
                        logger.info(f"[VOUCHER_ADD] SUCCESS: Applied general UserVoucher {user_voucher.id} to cart {cart.id}")
                        messages.success(request, f"Voucher '{voucher_code}' applied successfully.")

        except Voucher.DoesNotExist:
            logger.warning(f"[VOUCHER_ADD] FAILED: Voucher code '{voucher_code}' not found.")
            messages.error(request, f"Voucher code '{voucher_code}' is invalid.")
            cart.active_voucher = None
            cart.save()

        return redirect('cart_detail')

    # Handle GET request or other cases
    return redirect('cart_detail')

@staff_member_required
@require_http_methods(["GET", "POST"])
def assign_vouchers_to_users(request):
    """Admin view for assigning vouchers to specific users"""
    voucher_ids = request.GET.get('voucher_ids', '').split(',')
    vouchers = Voucher.objects.filter(id__in=voucher_ids, voucher_type='dedicated')
    
    if not vouchers.exists():
        messages.error(request, "No valid dedicated vouchers selected")
        return redirect('admin:store_voucher_changelist')
    
    if request.method == 'POST':
        user_ids = request.POST.getlist('user_ids')
        if not user_ids:
            messages.error(request, "Please select at least one user")
            return render(request, 'admin/assign_vouchers.html', {'vouchers': vouchers})
        
        users = User.objects.filter(id__in=user_ids)
        count = 0
        
        # Create UserVoucher entries for each user-voucher pair
        for voucher in vouchers:
            for user in users:
                # Check if this assignment already exists
                if not UserVoucher.objects.filter(user=user, voucher=voucher).exists():
                    UserVoucher.objects.create(user=user, voucher=voucher)
                    count += 1
        
        messages.success(request, f"Successfully assigned {count} vouchers to users")
        return redirect('admin:store_uservoucher_changelist')
    
    # GET request - display form
    # Get users that don't already have these vouchers
    existing_assignments = UserVoucher.objects.filter(voucher__in=vouchers).values_list('user_id', 'voucher_id')
    existing_pairs = set((user_id, voucher_id) for user_id, voucher_id in existing_assignments)
    
    # Filter active users
    users = User.objects.filter(is_active=True).order_by('username')
    
    # Mark users who already have some of the vouchers
    for user in users:
        user.has_some_vouchers = any((user.id, voucher.id) in existing_pairs for voucher in vouchers)
    
    return render(request, 'admin/assign_vouchers.html', {
        'vouchers': vouchers,
        'users': users,
        'title': 'Assign Vouchers to Users',
    })

@staff_member_required
def voucher_guide(request):
    """Admin view to display the voucher management guide"""
    context = {
        'title': 'Voucher Management Guide',
        'voucher_count': Voucher.objects.count(),
        'general_voucher_count': Voucher.objects.filter(voucher_type='general').count(),
        'dedicated_voucher_count': Voucher.objects.filter(voucher_type='dedicated').count(),
        'active_voucher_count': Voucher.objects.filter(is_active=True).count(),
    }
    return render(request, 'admin/voucher_guide.html', context)

@login_required
def edit_profile(request):
    """Edit user profile information"""
    user = request.user
    profile = UserProfile.objects.get(user=user)
    
    if request.method == 'POST':
        # Get form data
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone_number = request.POST.get('phone_number')
        
        # Update user model
        user.first_name = first_name
        user.last_name = last_name
        user.save()
        
        # Update profile model
        profile.phone_number = phone_number
        profile.save()
        
        messages.success(request, 'Your profile has been updated.')
        return redirect('profile')
    
    context = {
        'user': user,
        'profile': profile,
    }
    return render(request, 'store/edit_profile.html', context)

# Add a custom password change view
class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'store/password_change_form.html'
    success_url = '/profile/'  # Redirect to profile page after successful password change
    
    def form_valid(self, form):
        messages.success(self.request, 'Your password has been changed successfully!')
        
        # Create a notification for password change
        if self.request.user.is_authenticated:
            from store.models import Notification
            Notification.objects.create(
                user=self.request.user,
                title="Password Changed",
                message="Your password was successfully changed. If you did not make this change, please contact support immediately.",
                notification_type='security',
                is_read=False
            )
        
        return super().form_valid(form)

@login_required
def add_rating(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # Check if user has already rated this product
    existing_rating = ProductRating.objects.filter(product=product, user=request.user).first()
    if existing_rating:
        messages.warning(request, 'You have already rated this product.')
        return redirect('product_detail', slug=product.slug)
    
    # Check if the user has purchased this product
    has_purchased = OrderItem.objects.filter(
        order__user=request.user,
        product=product,
        order__status__in=['processing', 'shipped', 'delivered']
    ).exists()
    
    if not has_purchased:
        messages.warning(request, 'You can only rate products you have purchased.')
        return redirect('product_detail', slug=product.slug)
    
    if request.method == 'POST':
        form = ProductRatingForm(request.POST)
        if form.is_valid():
            rating = form.save(commit=False)
            rating.product = product
            rating.user = request.user
            rating.save()
            
            # Update product's average rating
            product.update_rating()
            
            messages.success(request, 'Thank you for your review! Your feedback helps other shoppers.')
        else:
            messages.error(request, 'There was an error with your rating. Please try again.')
    
    return redirect('product_detail', slug=product.slug)

@login_required
def edit_rating(request, rating_id):
    rating = get_object_or_404(ProductRating, id=rating_id, user=request.user)
    product = rating.product
    
    if request.method == 'POST':
        form = ProductRatingForm(request.POST, instance=rating)
        if form.is_valid():
            form.save()
            
            # Update product's average rating
            product.update_rating()
            
            messages.success(request, 'Your review has been updated successfully.')
        else:
            messages.error(request, 'There was an error updating your review. Please try again.')
    
    return redirect('product_detail', slug=product.slug)

@login_required
def delete_rating(request, rating_id):
    rating = get_object_or_404(ProductRating, id=rating_id, user=request.user)
    product = rating.product
    
    if request.method == 'POST':
        rating.delete()
        
        # Update product's average rating
        product.update_rating()
        
        messages.success(request, 'Your review has been deleted successfully.')
    
    return redirect('product_detail', slug=product.slug)

# Package views
def package_list(request):
    packages = Package.objects.filter(is_active=True)
    categories = Category.objects.all()
    selected_category = None
    
    # Get filter parameters
    category_slug = request.GET.get('category')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    rating = request.GET.get('rating')
    sort = request.GET.get('sort', 'newest')
    
    # Apply category filter
    if category_slug:
        try:
            selected_category = Category.objects.get(slug=category_slug)
            packages = packages.filter(category=selected_category)
        except Category.DoesNotExist:
            pass
    
    # Apply price filters
    if min_price:
        try:
            packages = packages.filter(discounted_price__gte=float(min_price))
        except ValueError:
            pass
    
    if max_price:
        try:
            packages = packages.filter(discounted_price__lte=float(max_price))
        except ValueError:
            pass
    
    # Apply rating filter
    if rating:
        try:
            rating_value = int(rating)
            # Filter by the average_rating field
            packages = packages.filter(average_rating__gte=rating_value)
        except ValueError:
            pass
    
    # Apply sorting
    if sort == 'price_asc':
        packages = packages.order_by('discounted_price')
    elif sort == 'price_desc':
        packages = packages.order_by('-discounted_price')
    elif sort == 'popularity':
        packages = packages.annotate(
            sold_count=Count('orderpackage')
        ).order_by('-sold_count')
    else:  # Default to newest
        packages = packages.order_by('-created')
    
    context = {
        'packages': packages,
        'categories': categories,
        'selected_category': selected_category,
    }
    return render(request, 'store/package_list.html', context)

def package_detail(request, slug):
    package = get_object_or_404(Package, slug=slug, is_active=True)
    package_products = PackageProduct.objects.filter(package=package).select_related('product')
    comments = PackageComment.objects.filter(package=package).order_by('-created_at')
    comment_form = CommentForm()
    
    # Get package ratings
    ratings = PackageRating.objects.filter(package=package).select_related('user').order_by('-created_at')
    
    # Check if user has already rated this package
    user_has_rated = False
    user_rating = None
    if request.user.is_authenticated:
        user_rating = PackageRating.objects.filter(package=package, user=request.user).first()
        user_has_rated = user_rating is not None
        
        # Check if user has purchased this package
        user_has_purchased = OrderPackage.objects.filter(
            order__user=request.user,
            package=package,
            order__status__in=['processing', 'shipped', 'delivered']
        ).exists()
    else:
        user_has_purchased = False
    
    # Initialize rating form if user hasn't rated yet
    rating_form = None
    if request.user.is_authenticated and not user_has_rated and user_has_purchased:
        rating_form = ProductRatingForm()  # Using the same form as products
    
    return render(request, 'store/package_detail.html', {
        'package': package,
        'package_products': package_products,
        'comments': comments,
        'comment_form': comment_form,
        'ratings': ratings,
        'rating_form': rating_form,
        'user_has_rated': user_has_rated,
        'user_rating': user_rating,
        'user_has_purchased': user_has_purchased,
    })

def customize_package(request, slug):
    package = get_object_or_404(Package, slug=slug, is_active=True)
    package_products = PackageProduct.objects.filter(package=package).select_related('product')
    
    # Create or get customized package
    customized_package = None
    if request.user.is_authenticated:
        customized_package, created = CustomizedPackage.objects.get_or_create(
            user=request.user,
            original_package=package
        )
        
        # If created, initialize with package products
        if created:
            for pp in package_products:
                CustomizedPackageItem.objects.create(
                    customized_package=customized_package,
                    product=pp.product,
                    quantity=pp.quantity
                )
    
    # Handle form submission for customizing package
    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.error(request, "Please login to customize this package.")
            return redirect('login')
        
        # Get product IDs from form
        selected_products = request.POST.getlist('product')
        quantities = {}
        
        # Get quantities for each product
        for key, value in request.POST.items():
            if key.startswith('quantity_') and value.isdigit():
                product_id = key.replace('quantity_', '')
                quantities[product_id] = int(value)
        
        # Clear existing items (if any)
        CustomizedPackageItem.objects.filter(customized_package=customized_package).delete()
        
        # Add selected products
        for product_id in selected_products:
            product = Product.objects.get(id=product_id)
            quantity = quantities.get(product_id, 1)
            CustomizedPackageItem.objects.create(
                customized_package=customized_package,
                product=product,
                quantity=quantity
            )
        
        # Check if meets minimum purchase amount
        if customized_package.meets_minimum_requirement():
            messages.success(request, "Your package has been customized successfully.")
            return redirect('add_customized_package_to_cart', customized_package_id=customized_package.id)
        else:
            messages.error(request, f"Your package must have a minimum value of ${package.minimum_purchase_amount}.")
    
    # Calculate total value of customized package (if any)
    customized_package_items = []
    customized_package_total = 0
    if customized_package:
        customized_package_items = CustomizedPackageItem.objects.filter(customized_package=customized_package).select_related('product')
        customized_package_total = sum(item.product.price * item.quantity for item in customized_package_items)
    
    return render(request, 'store/customize_package.html', {
        'package': package,
        'package_products': package_products,
        'customized_package': customized_package,
        'customized_package_items': customized_package_items,
        'customized_package_total': customized_package_total,
        'minimum_purchase_amount': package.minimum_purchase_amount
    })

def add_package_to_cart(request, package_id):
    if request.method == 'POST':
        package = get_object_or_404(Package, id=package_id, is_active=True)
        
        # Get or create cart
        cart = get_or_create_cart(request)
        
        # Check if all products in the package have enough stock
        package_products = PackageProduct.objects.filter(package=package).select_related('product')
        out_of_stock_items = []
        max_quantity_allowed = float('inf')  # Start with infinity
        
        # Check each product's stock and determine max quantity
        for pp in package_products:
            # Calculate how many packages can be created with current stock
            if pp.quantity > 0:  # Prevent division by zero
                possible_packages = pp.product.stock // pp.quantity
                max_quantity_allowed = min(max_quantity_allowed, possible_packages)
            
            if pp.product.stock < pp.quantity:
                out_of_stock_items.append(f"{pp.product.name} (required: {pp.quantity}, available: {pp.product.stock})")
        
        # If any products are out of stock, show error and don't add to cart
        if out_of_stock_items:
            # Create a single consolidated message
            out_of_stock_message = f"Cannot add package '{package.name}' to cart due to insufficient stock:"
            for item in out_of_stock_items[:3]:  # Show only first 3 items to keep notification compact
                out_of_stock_message += f"\n• {item}"
                
            # Add a note if there are more items than we're showing
            if len(out_of_stock_items) > 3:
                out_of_stock_message += f"\n• And {len(out_of_stock_items) - 3} more items..."
                
            messages.error(request, out_of_stock_message)
            return redirect('package_detail', slug=package.slug)
        
        # Check if package already in cart - handle possible duplicates
        existing_packages = CartPackage.objects.filter(cart=cart, package=package)
        current_quantity = existing_packages.count()
        
        # Check if adding one more would exceed max allowed quantity
        if current_quantity >= max_quantity_allowed:
            messages.warning(request, f"Cannot add more '{package.name}' packages. Limited to {max_quantity_allowed} due to product stock limitations.")
            return redirect('cart_detail')
        
        if existing_packages.exists():
            messages.info(request, f"{package.name} is already in your cart.")
            
            # If duplicates exist, clean them up by keeping only the first one
            if existing_packages.count() > 1:
                # Keep the first package and delete the rest
                first_package = existing_packages.first()
                duplicates = existing_packages.exclude(id=first_package.id)
                duplicates.delete()
        else:
            # Add package to cart
            cart_package = CartPackage.objects.create(cart=cart, package=package)
            
            # Add all package products to cart package
            for pp in package_products:
                CartPackageItem.objects.create(
                    cart_package=cart_package,
                    product=pp.product,
                    quantity=pp.quantity
                )
            
            messages.success(request, f"{package.name} has been added to your cart.")
    
    return redirect('cart_detail')

def add_customized_package_to_cart(request, customized_package_id):
    customized_package = get_object_or_404(CustomizedPackage, id=customized_package_id, user=request.user)
    
    # Check if meets minimum purchase requirement
    if not customized_package.meets_minimum_requirement():
        messages.error(request, f"Your package must have a minimum value of ${customized_package.original_package.minimum_purchase_amount}.")
        return redirect('customize_package', slug=customized_package.original_package.slug)
    
    # Get or create cart
    cart = get_or_create_cart(request)
    
    # Create cart package
    cart_package = CartPackage.objects.create(
        cart=cart,
        package=customized_package.original_package
    )
    
    # Add customized items to cart package
    customized_items = CustomizedPackageItem.objects.filter(customized_package=customized_package)
    for item in customized_items:
        CartPackageItem.objects.create(
            cart_package=cart_package,
            product=item.product,
            quantity=item.quantity
        )
    
    messages.success(request, f"Your customized {customized_package.original_package.name} has been added to your cart.")
    return redirect('cart_detail')

def remove_package_from_cart(request, package_id):
    if request.method == 'POST':
        package = get_object_or_404(Package, id=package_id)
        cart = get_or_create_cart(request)
        
        try:
            cart_package = CartPackage.objects.get(cart=cart, package=package)
            cart_package.delete()
            messages.success(request, f"{package.name} has been removed from your cart.")
        except CartPackage.DoesNotExist:
            messages.error(request, "Package not found in your cart.")
    
    return redirect('cart_detail')

def update_package_quantity(request, cart_package_id):
    """Update the quantity of a package in the cart."""
    cart_package = get_object_or_404(CartPackage, id=cart_package_id)
    
    # Security check - ensure user owns this cart package
    cart = get_or_create_cart(request)
    if cart_package.cart.id != cart.id:
        messages.error(request, "You don't have permission to modify this cart item.")
        return redirect('cart_detail')
    
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        if quantity < 1:
            quantity = 1
        
        # Find all existing cart packages of the same type (including the current one)
        all_packages = CartPackage.objects.filter(
            cart=cart, 
            package=cart_package.package
        )
        
        # Keep a record of all its items to duplicate if needed
        original_items = list(cart_package.items.all())
        
        # Calculate maximum allowed packages based on product stock
        package_products = PackageProduct.objects.filter(package=cart_package.package).select_related('product')
        max_quantity_allowed = float('inf')  # Start with infinity
        
        for pp in package_products:
            if pp.quantity > 0:  # Prevent division by zero
                possible_packages = pp.product.stock // pp.quantity
                max_quantity_allowed = min(max_quantity_allowed, possible_packages)
        
        # Limit the requested quantity to the maximum allowed
        if quantity > max_quantity_allowed:
            quantity = max_quantity_allowed
            messages.warning(request, f"Quantity limited to {max_quantity_allowed} due to product stock limitations.")
        
        # If there are duplicate packages, clean them up first
        if all_packages.count() > 1:
            # Keep the current package, delete all others
            to_delete = all_packages.exclude(id=cart_package.id)
            to_delete.delete()
            
            # Reset all_packages
            all_packages = CartPackage.objects.filter(id=cart_package.id)
        
        current_quantity = all_packages.count()
        
        # If quantity is less than current and current is > 1, remove the current package
        if quantity < current_quantity:
            if quantity == 0:
                # Remove the package entirely
                cart_package.delete()
                messages.success(request, f"Removed {cart_package.package.name} from your cart.")
            else:
                # We shouldn't get here since we cleaned up duplicates above
                # and the quantity should be 1, but just in case:
                messages.success(request, f"Updated {cart_package.package.name} quantity to {quantity}.")
        
        # If quantity is more than current, add more packages
        elif quantity > current_quantity:
            # How many to add
            to_add = quantity - current_quantity
            
            # Create additional cart packages to represent quantity
            for _ in range(to_add):
                new_package = CartPackage.objects.create(
                    cart=cart,
                    package=cart_package.package
                )
                
                # Copy all items from the original package
                for item in original_items:
                    CartPackageItem.objects.create(
                        cart_package=new_package,
                        product=item.product,
                        quantity=item.quantity
                    )
                
            messages.success(request, f"Updated {cart_package.package.name} quantity to {quantity}.")
        
    return redirect('cart_detail')

def add_package_comment(request, package_id):
    package = get_object_or_404(Package, id=package_id)
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = PackageComment(
                package=package,
                user=request.user,
                text=form.cleaned_data['text']
            )
            comment.save()
            messages.success(request, "Your comment has been added.")
        else:
            messages.error(request, "There was an error with your comment submission.")
    
    return redirect('package_detail', slug=package.slug)

def add_package_rating(request, package_id):
    package = get_object_or_404(Package, id=package_id)
    
    # Check if user has purchased this package
    if request.user.is_authenticated:
        has_purchased = OrderPackage.objects.filter(
            order__user=request.user,
            package=package,
            order__status__in=['processing', 'shipped', 'delivered']
        ).exists()
        
        if not has_purchased:
            messages.error(request, "You can only rate packages you have purchased.")
            return redirect('package_detail', slug=package.slug)
    else:
        messages.error(request, "You must be logged in to rate packages.")
        return redirect('login')
    
    # Check if user has already rated this package
    existing_rating = PackageRating.objects.filter(package=package, user=request.user).first()
    if existing_rating:
        messages.error(request, "You have already rated this package.")
        return redirect('package_detail', slug=package.slug)
    
    if request.method == 'POST':
        form = ProductRatingForm(request.POST)
        if form.is_valid():
            rating = PackageRating(
                package=package,
                user=request.user,
                rating=form.cleaned_data['rating'],
                feedback=form.cleaned_data['feedback']
            )
            rating.save()
            messages.success(request, "Your rating has been submitted. Thank you for your feedback!")
        else:
            messages.error(request, "There was an error with your rating submission.")
    
    return redirect('package_detail', slug=package.slug)

def edit_package_rating(request, rating_id):
    rating = get_object_or_404(PackageRating, id=rating_id, user=request.user)
    
    if request.method == 'POST':
        form = ProductRatingForm(request.POST)
        if form.is_valid():
            rating.rating = form.cleaned_data['rating']
            rating.feedback = form.cleaned_data['feedback']
            rating.save()
            messages.success(request, "Your rating has been updated.")
        else:
            messages.error(request, "There was an error updating your rating.")
    
    return redirect('package_detail', slug=rating.package.slug)

def delete_package_rating(request, rating_id):
    rating = get_object_or_404(PackageRating, id=rating_id, user=request.user)
    package_slug = rating.package.slug
    
    if request.method == 'POST':
        rating.delete()
        messages.success(request, "Your rating has been deleted.")
    
    return redirect('package_detail', slug=package_slug)

@require_POST
def logout_view(request):
    """
    Custom logout view that only accepts POST requests
    """
    logout(request)
    return HttpResponseRedirect(reverse('home'))

@login_required
def unread_notifications_count(request):
    """API endpoint to get unread notifications count by type"""
    if not request.user.is_authenticated:
        return JsonResponse({'total_count': 0, 'security_count': 0})
        
    # Get total unread count
    total_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    # Get security notifications count
    security_count = Notification.objects.filter(
        user=request.user,
        is_read=False,
        notification_type='security'
    ).count()
    
    return JsonResponse({
        'total_count': total_count,
        'security_count': security_count
    })

# Add at the end of the file

@login_required
def api_notifications(request):
    """API endpoint to fetch user notifications"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    user = request.user
    # Get all notifications for this user
    all_notifications = Notification.objects.filter(user=user)
    
    # Count unread notifications before slicing
    unread_count = all_notifications.filter(is_read=False).count()
    
    # Get just the 10 most recent notifications for display
    notifications = all_notifications.order_by('-created_at')[:10]
    
    notification_data = []
    for notification in notifications:
        notification_data.append({
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'url': notification.link or '#',
            'type': notification.notification_type,
            'is_read': notification.is_read,
            'created_at': notification.created_at.strftime('%Y-%m-%d %H:%M'),
            'time_ago': get_time_ago(notification.created_at)
        })
    
    return JsonResponse({
        'unread_count': unread_count,
        'notifications': notification_data
    })

@login_required
def api_mark_all_notifications_read(request):
    """API endpoint to mark all notifications as read"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    
    return JsonResponse({'success': True})

def get_time_ago(timestamp):
    """Convert timestamp to human-readable time ago string"""
    now = timezone.now()
    diff = now - timestamp
    
    seconds = diff.total_seconds()
    if seconds < 60:
        return 'Just now'
    
    minutes = seconds // 60
    if minutes < 60:
        return f'{int(minutes)} minute{"s" if minutes > 1 else ""} ago'
    
    hours = minutes // 60
    if hours < 24:
        return f'{int(hours)} hour{"s" if hours > 1 else ""} ago'
    
    days = hours // 24
    if days < 7:
        return f'{int(days)} day{"s" if days > 1 else ""} ago'
    
    weeks = days // 7
    if weeks < 4:
        return f'{int(weeks)} week{"s" if weeks > 1 else ""} ago'
    
    months = days // 30
    if months < 12:
        return f'{int(months)} month{"s" if months > 1 else ""} ago'
    
    years = days // 365
    return f'{int(years)} year{"s" if years > 1 else ""} ago'
