from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import (
    Category, Product, Comment, Cart, CartItem, Order, OrderItem, 
    ShippingAddress, PromoBanner, UserProfile, Voucher, CreditCard,
    Notification, UserVoucher, CommentResponse, Package, PackageProduct,
    PackageRating, PackageComment, CustomizedPackage, CustomizedPackageItem,
    OrderPackage, OrderPackageItem, CartPackage, CartPackageItem
)
from django.urls import reverse
from django.http import HttpResponseRedirect
from urllib.parse import urlencode
from django import forms
from django.utils import timezone
from django.utils.html import format_html
from django.urls import path
from django.http import JsonResponse
from django.db.models import Sum, Count, F
from django.shortcuts import render

# Custom admin site
class CustomAdminSite(admin.AdminSite):
    site_header = "E-Commerce Administration"
    site_title = "E-Commerce Admin Portal"
    index_title = "Welcome to E-Commerce Admin Portal"
    
    def each_context(self, request):
        context = super().each_context(request)
        context['voucher_guide_url'] = reverse('voucher_guide')
        context['package_dashboard_url'] = reverse('admin:package_sales_dashboard')
        return context
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('package-sales-dashboard/', self.admin_view(self.package_sales_dashboard), name='package_sales_dashboard'),
            path('api/package-sales-data/', self.admin_view(self.package_sales_data), name='package_sales_data'),
        ]
        return custom_urls + urls
    
    def package_sales_dashboard(self, request):
        """View for package sales dashboard"""
        context = self.each_context(request)
        context['title'] = 'Package Sales Dashboard'
        
        # Get all packages for the dropdown filter
        context['packages'] = Package.objects.all().order_by('name')
        
        # Date filter defaults
        today = timezone.now()
        start_date = request.GET.get('start_date', (today - timezone.timedelta(days=30)).strftime('%Y-%m-%d'))
        end_date = request.GET.get('end_date', today.strftime('%Y-%m-%d'))
        
        context['start_date'] = start_date
        context['end_date'] = end_date
        
        # Summary metrics
        total_packages_sold = OrderPackage.objects.count()
        revenue_from_packages = OrderPackage.objects.aggregate(Sum('price'))['price__sum'] or 0
        
        context['total_packages_sold'] = total_packages_sold
        context['revenue_from_packages'] = revenue_from_packages
        
        return render(request, 'admin/package_sales_dashboard.html', context)
    
    def package_sales_data(self, request):
        """API endpoint for package sales data"""
        # Date filter
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        package_id = request.GET.get('package_id')
        
        # Base query
        query = OrderPackage.objects.all()
        
        # Apply filters
        if start_date:
            query = query.filter(created_at__gte=start_date)
        if end_date:
            # Add one day to include the end date entirely
            end_date_obj = timezone.datetime.strptime(end_date, '%Y-%m-%d')
            end_date_obj = end_date_obj + timezone.timedelta(days=1)
            query = query.filter(created_at__lt=end_date_obj)
        if package_id and package_id != 'all':
            query = query.filter(package_id=package_id)
        
        # Sales by package
        sales_by_package = query.values('package__name').annotate(
            count=Count('id'),
            revenue=Sum('price')
        ).order_by('-count')
        
        # Sales over time (by day)
        from django.db.models.functions import TruncDay
        sales_over_time = query.annotate(date=TruncDay('created_at')).values('date').annotate(
            count=Count('id'),
            revenue=Sum('price')
        ).order_by('date')
        
        # Top selling products within packages
        top_products = OrderPackageItem.objects.filter(order_package__in=query).values(
            'product__name'
        ).annotate(
            count=Sum('quantity'),
            revenue=Sum(F('price') * F('quantity'))
        ).order_by('-count')[:10]
        
        return JsonResponse({
            'sales_by_package': list(sales_by_package),
            'sales_over_time': list(sales_over_time),
            'top_products': list(top_products),
        })

# Use the custom admin site
admin_site = CustomAdminSite(name='custom_admin')

# Register User model with custom admin site
admin_site.register(User, UserAdmin)

# Register models with custom_admin_site
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_number', 'role', 'is_email_verified']
    list_filter = ['role', 'is_email_verified']
    search_fields = ['user__username', 'user__email', 'phone_number']
    raw_id_fields = ['user']

admin_site.register(UserProfile, UserProfileAdmin)

class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}

admin_site.register(Category, CategoryAdmin)

class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'category', 'original_price', 'price', 'is_active', 'is_featured', 'rating', 'sold_count']
    list_filter = ['is_active', 'is_featured', 'rating', 'category']
    list_editable = ['price', 'original_price', 'category', 'is_active', 'is_featured', 'rating']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name', 'description']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'category', 'image')
        }),
        ('Pricing', {
            'fields': ('original_price', 'price')
        }),
        ('Status', {
            'fields': ('is_active', 'is_featured', 'stock')
        }),
        ('Metrics', {
            'fields': ('rating', 'sold_count')
        }),
    )

admin_site.register(Product, ProductAdmin)

class CommentAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'product__name', 'text']

admin_site.register(Comment, CommentAdmin)

class CartItemInline(admin.TabularInline):
    model = CartItem
    raw_id_fields = ['product']
    extra = 0

class CartAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'session_id', 'created_at', 'item_count', 'total_price']
    list_filter = ['created_at']
    inlines = [CartItemInline]
    
    def item_count(self, obj):
        return obj.items.count()
    
    def total_price(self, obj):
        return f"${obj.total_price}"

admin_site.register(Cart, CartAdmin)

class PromoBannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'active', 'order', 'created_at')
    list_filter = ('active',)
    search_fields = ('title', 'subtitle')
    ordering = ('order', 'created_at')

admin_site.register(PromoBanner, PromoBannerAdmin)

class VoucherForm(forms.ModelForm):
    class Meta:
        model = Voucher
        fields = '__all__'
        widgets = {
            'valid_from': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'valid_to': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'min_purchase_amount': forms.NumberInput(attrs={'step': '0.01'}),
            'discount_value': forms.NumberInput(attrs={'step': '0.01'}),
            'max_discount': forms.NumberInput(attrs={'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default dates if creating a new voucher
        if not kwargs.get('instance'):
            self.fields['valid_from'].initial = timezone.now().strftime('%Y-%m-%dT%H:%M')
            self.fields['valid_to'].initial = (timezone.now() + timezone.timedelta(days=30)).strftime('%Y-%m-%dT%H:%M')
        
        # Add placeholders and help text
        self.fields['code'].widget.attrs.update({'placeholder': 'e.g., SUMMER25'})
        self.fields['min_purchase_amount'].widget.attrs.update({'placeholder': '0.00'})
        self.fields['discount_value'].widget.attrs.update({'placeholder': '10.00'})
        self.fields['usage_limit'].widget.attrs.update({'placeholder': '1'})

class VoucherAdmin(admin.ModelAdmin):
    form = VoucherForm
    list_display = [
        'code', 'voucher_type', 'discount_type', 'discount_value', 'valid_from', 'valid_to', 
        'is_active', 'used_count', 'usage_limit', 'is_valid', 'guide_link'
    ]
    list_filter = ['voucher_type', 'is_active', 'discount_type', 'valid_from', 'valid_to']
    search_fields = ['code']
    readonly_fields = ['used_count']
    fieldsets = (
        ('Voucher Type', {
            'fields': ('voucher_type', 'code'),
            'classes': ('wide',),
            'description': 'Choose whether this is a general voucher available to all users or a dedicated voucher for specific users.'
        }),
        ('Discount Details', {
            'fields': ('discount_type', 'discount_value', 'max_discount'),
            'description': 'For percentage discounts, you can set a maximum discount amount.'
        }),
        ('Validity', {
            'fields': ('valid_from', 'valid_to', 'is_active'),
            'description': 'Set when this voucher becomes valid and when it expires.'
        }),
        ('Usage Settings', {
            'fields': ('min_purchase_amount', 'usage_limit', 'used_count'),
            'description': 'Control how the voucher can be used.'
        }),
    )
    
    actions = ['assign_to_users', 'duplicate_voucher']
    
    def guide_link(self, obj):
        return format_html('<a href="{}">Voucher Guide</a>', reverse('voucher_guide'))
    guide_link.short_description = "Help"
    
    def assign_to_users(self, request, queryset):
        # Only allow for dedicated vouchers
        dedicated_vouchers = queryset.filter(voucher_type='dedicated')
        if not dedicated_vouchers:
            self.message_user(request, "Please select dedicated vouchers only for this action.", level='error')
            return
            
        # Form to handle user selection will be displayed
        return HttpResponseRedirect(reverse('assign_vouchers') + 
                                  '?' + urlencode({'voucher_ids': ','.join(str(v.pk) for v in dedicated_vouchers)}))
    
    assign_to_users.short_description = "Assign selected vouchers to users"
    
    def duplicate_voucher(self, request, queryset):
        """Create copies of selected vouchers with new codes"""
        count = 0
        for voucher in queryset:
            # Create a copy with a new code
            new_code = f"{voucher.code}_COPY{count+1}"
            voucher_copy = Voucher.objects.create(
                code=new_code,
                voucher_type=voucher.voucher_type,
                discount_type=voucher.discount_type,
                discount_value=voucher.discount_value,
                max_discount=voucher.max_discount,
                valid_from=voucher.valid_from,
                valid_to=voucher.valid_to,
                is_active=voucher.is_active,
                min_purchase_amount=voucher.min_purchase_amount,
                usage_limit=voucher.usage_limit,
                used_count=0  # Reset usage count
            )
            count += 1
        
        self.message_user(request, f"Successfully duplicated {count} vouchers.")
    
    duplicate_voucher.short_description = "Duplicate selected vouchers"
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        
        # When creating a new voucher (obj=None), customize the form
        if obj is None:
            form.base_fields['is_active'].initial = True
            form.base_fields['usage_limit'].initial = 1
            
            # Disable the used_count field when creating new vouchers
            if 'used_count' in form.base_fields:
                form.base_fields['used_count'].disabled = True
                form.base_fields['used_count'].initial = 0
                
        return form

admin_site.register(Voucher, VoucherAdmin)

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ['product']
    readonly_fields = ['price', 'quantity']
    extra = 0

class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_number', 'user', 'status', 'payment_status', 
        'shipping_fee', 'voucher_discount', 'total_price', 'created_at'
    ]
    list_filter = ['status', 'payment_status', 'created_at']
    search_fields = ['order_number', 'user__username', 'user__email']
    readonly_fields = ['order_number', 'voucher_discount', 'barcode']
    inlines = [OrderItemInline]
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'user', 'shipping_address', 'status', 'payment_status', 'payment_method')
        }),
        ('Financial', {
            'fields': ('shipping_fee', 'voucher', 'voucher_discount')
        }),
        ('Additional Information', {
            'fields': ('notes', 'barcode')
        }),
    )

admin_site.register(Order, OrderAdmin)

class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'phone_number', 'city', 'country', 'is_default']
    list_filter = ['is_default', 'country', 'city']
    search_fields = ['name', 'user__username', 'phone_number', 'address_line1', 'city']
    raw_id_fields = ['user']

admin_site.register(ShippingAddress, ShippingAddressAdmin)

class CreditCardAdmin(admin.ModelAdmin):
    list_display = ['masked_number', 'card_holder', 'user', 'expiry_date', 'is_default']
    list_filter = ['is_default', 'expiry_year', 'expiry_month']
    search_fields = ['card_holder', 'user__username']
    raw_id_fields = ['user']
    readonly_fields = ['masked_number']

admin_site.register(CreditCard, CreditCardAdmin)

class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'created_at']
    list_filter = ['created_at']
    search_fields = ['title']

admin_site.register(Notification, NotificationAdmin)

class UserVoucherAdmin(admin.ModelAdmin):
    list_display = ('user', 'voucher', 'voucher_type', 'voucher_discount', 'voucher_expiry', 'is_used', 'created_at')
    list_filter = ('is_used', 'voucher__voucher_type', 'voucher__is_active', 'user')
    search_fields = ('user__username', 'user__email', 'voucher__code')
    autocomplete_fields = ['user', 'voucher']
    
    def voucher_type(self, obj):
        return obj.voucher.get_voucher_type_display()
    voucher_type.short_description = "Voucher Type"
    
    def voucher_discount(self, obj):
        if obj.voucher.discount_type == 'percentage':
            return f"{obj.voucher.discount_value}%"
        else:
            return f"${obj.voucher.discount_value}"
    voucher_discount.short_description = "Discount"
    
    def voucher_expiry(self, obj):
        return obj.voucher.valid_to
    voucher_expiry.short_description = "Expires On"

admin_site.register(UserVoucher, UserVoucherAdmin)

class CommentResponseInline(admin.TabularInline):
    model = CommentResponse
    extra = 0
    readonly_fields = ('user', 'created_at')

class CommentResponseAdmin(admin.ModelAdmin):
    list_display = ('comment', 'user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('text', 'comment__text', 'user__username')
    raw_id_fields = ('comment', 'user')

admin_site.register(CommentResponse, CommentResponseAdmin)

class PackageProductInline(admin.TabularInline):
    model = PackageProduct
    raw_id_fields = ['product']
    extra = 1

class PackageAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'category', 'original_price', 'discounted_price', 'is_active', 'is_featured', 'sold_count']
    list_filter = ['is_active', 'is_featured', 'category']
    list_editable = ['discounted_price', 'original_price', 'category', 'is_active', 'is_featured']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name', 'description']
    inlines = [PackageProductInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'category', 'image')
        }),
        ('Pricing', {
            'fields': ('original_price', 'discounted_price', 'minimum_purchase_amount')
        }),
        ('Status', {
            'fields': ('is_active', 'is_featured')
        }),
        ('Metrics', {
            'fields': ('average_rating', 'total_ratings', 'sold_count')
        }),
    )

admin_site.register(Package, PackageAdmin)

class OrderPackageItemInline(admin.TabularInline):
    model = OrderPackageItem
    raw_id_fields = ['product']
    extra = 0

class OrderPackageAdmin(admin.ModelAdmin):
    list_display = ['order', 'package', 'price', 'created_at']
    search_fields = ['order__order_number', 'package__name']
    inlines = [OrderPackageItemInline]

admin_site.register(OrderPackage, OrderPackageAdmin)

class PackageRatingAdmin(admin.ModelAdmin):
    list_display = ['user', 'package', 'rating', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['user__username', 'package__name', 'feedback']

admin_site.register(PackageRating, PackageRatingAdmin)

class PackageCommentAdmin(admin.ModelAdmin):
    list_display = ['user', 'package', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'package__name', 'text']

admin_site.register(PackageComment, PackageCommentAdmin)

class CustomizedPackageItemInline(admin.TabularInline):
    model = CustomizedPackageItem
    raw_id_fields = ['product']
    extra = 1

class CustomizedPackageAdmin(admin.ModelAdmin):
    list_display = ['original_package', 'user', 'total_price', 'created_at']
    search_fields = ['user__username', 'original_package__name']
    inlines = [CustomizedPackageItemInline]

admin_site.register(CustomizedPackage, CustomizedPackageAdmin)

class CartPackageItemInline(admin.TabularInline):
    model = CartPackageItem
    raw_id_fields = ['product']
    extra = 0

class CartPackageAdmin(admin.ModelAdmin):
    list_display = ['cart', 'package', 'total_price', 'created_at']
    search_fields = ['cart__id', 'package__name']
    inlines = [CartPackageItemInline]

admin_site.register(CartPackage, CartPackageAdmin)
