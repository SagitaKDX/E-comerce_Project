from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.text import slugify
from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image
import os
import barcode
from barcode.writer import ImageWriter
from io import BytesIO
from django.core.files import File
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class UserProfile(models.Model):
    USER_ROLES = (
        ('customer', 'Customer'),
        ('crm_user', 'CRM User'),
        ('csr', 'Customer Service Representative'),
        ('staff', 'Staff'),
        ('admin', 'Admin'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=20, choices=USER_ROLES, default='customer')
    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=100, blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username}'s profile"
    
    def is_csr(self):
        return self.role in ['csr', 'staff', 'admin'] or self.user.is_staff
        
    def is_crm_user(self):
        return self.role in ['crm_user', 'csr', 'staff', 'admin'] or self.user.is_staff

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=50, unique=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    
    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('category_detail', kwargs={'slug': self.slug})
    
    def get_products(self):
        """Get active products in this category"""
        return self.products.filter(is_active=True)
        
    def get_packages(self):
        """Get active packages in this category"""
        return self.packages.filter(is_active=True)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
        if self.image:
            try:
                img = Image.open(self.image.path)
                if img.height > 400 or img.width > 400:
                    output_size = (400, 400)
                    img.thumbnail(output_size, Image.Resampling.LANCZOS)
                    img.save(self.image.path, quality=85)
            except (IOError, OSError) as e:
                # Log the error but don't prevent saving
                logger.error(f"Error processing image for category {self.name}: {str(e)}")

class Product(models.Model):
    RATING_CHOICES = [(i, i) for i in range(1, 6)]
    
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField()
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    category = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE)
    stock = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, default=5)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_ratings = models.PositiveIntegerField(default=0)
    sold_count = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('product_detail', kwargs={'slug': self.slug})
    
    def update_rating(self):
        """Update the average rating and total ratings count for this product"""
        ratings = self.ratings.all()
        if ratings.exists():
            total = sum(r.rating for r in ratings)
            count = ratings.count()
            self.average_rating = round(total / count, 2)
            self.total_ratings = count
            self.save(update_fields=['average_rating', 'total_ratings'])
        else:
            self.average_rating = 0
            self.total_ratings = 0
            self.save(update_fields=['average_rating', 'total_ratings'])
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
        if self.image:
            try:
                img = Image.open(self.image.path)
                if img.height > 800 or img.width > 800:
                    output_size = (800, 800)
                    img.thumbnail(output_size, Image.Resampling.LANCZOS)
                    img.save(self.image.path, quality=85)
            except (IOError, OSError) as e:
                # Log the error but don't prevent saving
                logger.error(f"Error processing image for product {self.name}: {str(e)}")

    @property
    def discount_amount(self):
        if self.original_price and self.original_price > self.price:
            return self.original_price - self.price
        return 0
    
    @property
    def discount_percent(self):
        if self.original_price and self.original_price > self.price:
            return round((self.original_price - self.price) / self.original_price * 100)
        return 0
    
    @property
    def final_price(self):
        return self.price

class ProductRating(models.Model):
    RATING_CHOICES = [(i, i) for i in range(1, 6)]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_ratings')
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, default=5)
    feedback = models.TextField(help_text="Share your experience with this product")
    staff_reviewed = models.BooleanField(default=False, help_text="Has this rating been reviewed by staff")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        # Ensure a user can only rate a product once
        unique_together = ['product', 'user']
    
    def __str__(self):
        return f"{self.user.username}'s {self.rating}-star rating for {self.product.name}"
    
    def save(self, *args, **kwargs):
        # Check if the user has purchased this product
        from .models import OrderItem
        has_purchased = OrderItem.objects.filter(
            order__user=self.user,
            product=self.product,
            order__status__in=['processing', 'shipped', 'delivered']
        ).exists()
        
        if not has_purchased:
            # If you want to raise an error, uncomment the line below
            # raise ValidationError("You can only rate products you have purchased")
            pass
            
        # Save the rating
        super().save(*args, **kwargs)
        
        # Update the product's average rating
        self.product.update_rating()

class Comment(models.Model):
    STATUS_CHOICES = (
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    is_private = models.BooleanField(default=False)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_comments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f'Comment by {self.user.username} on {self.product.name}'

class CommentResponse(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='responses')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    is_private = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f'Response by {self.user.username} on comment #{self.comment.id}'

class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_id = models.CharField(max_length=100, null=True, blank=True)
    active_voucher = models.ForeignKey('UserVoucher', related_name='carts', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Cart {self.id}"
    
    def get_subtotal(self):
        products_subtotal = sum(item.get_total() for item in self.items.all())
        packages_subtotal = sum(package.total_price for package in self.packages.all())
        return products_subtotal + packages_subtotal
    
    def get_voucher_discount(self):
        if not self.active_voucher:
            return 0
        
        # Use the voucher through UserVoucher relation
        if not self.active_voucher.is_valid:
            return 0
        
        return self.active_voucher.voucher.calculate_discount(self.get_subtotal())
    
    @property
    def total_quantity(self):
        # Sum quantities of all CartItems
        product_quantity = sum(item.quantity for item in self.items.all())
        # Add quantity from packages if applicable (assuming 1 per package for now)
        # You might need more complex logic if packages themselves have quantities
        package_quantity = self.packages.count() 
        return product_quantity + package_quantity

    @property
    def total_price(self):
        subtotal = self.get_subtotal()
        discount = self.get_voucher_discount() if self.active_voucher else 0
        return subtotal - discount
    
    @property
    def total_items(self):
        # Count total products
        product_items = sum(item.quantity for item in self.items.all())
        
        # Count packages - group by package id to handle duplicate packages
        package_groups = {}
        for package in self.packages.all():
            if package.package.id in package_groups:
                package_groups[package.package.id] += 1
            else:
                package_groups[package.package.id] = 1
                
        # Sum up the package counts
        package_items = sum(package_groups.values())
        
        return product_items + package_items

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    
    class Meta:
        unique_together = ['cart', 'product']
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name}"
    
    @property
    def total_price(self):
        return self.product.price * self.quantity
        
    def get_total(self):
        return self.product.price * self.quantity

class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    )
    order_number = models.CharField(max_length=25, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    shipping_address = models.ForeignKey('ShippingAddress', on_delete=models.PROTECT)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    order_notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.BooleanField(default=False)
    payment_method = models.CharField(max_length=50, default='Credit Card')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    voucher = models.ForeignKey('UserVoucher', null=True, blank=True, on_delete=models.SET_NULL)
    voucher_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    barcode = models.ImageField(upload_to='order_barcodes/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f'Order {self.order_number}'
    
    def get_subtotal(self):
        """Calculate subtotal from order items"""
        return sum(item.total_price for item in self.items.all())
    
    def get_total(self):
        """Calculate total price including shipping and discounts"""
        return self.subtotal + self.shipping_fee - self.voucher_discount
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            # Using 0 if id is None might lead to collisions if multiple unsaved orders exist concurrently.
            # Consider generating order_number after initial save or using UUID.
            order_id_for_num = self.id or 0
            self.order_number = f'ORD{timestamp}{order_id_for_num:04d}'
        
        # Removed the block that recalculated subtotal and total_price here,
        # as it overwrites the correct values passed during Order.objects.create
            
        super().save(*args, **kwargs) # Call super().save()
        
        # Generate barcode *after* saving ensures self.id and self.order_number are set
        # Make sure generate_barcode doesn't trigger save() recursively
        if not self.barcode and self.order_number: 
            self.generate_barcode()
    
    def generate_barcode(self):
        code128 = barcode.get('code128', self.order_number, writer=ImageWriter())
        buffer = BytesIO()
        code128.write(buffer)
        self.barcode.save(f'order_{self.order_number}.png', File(buffer), save=True)
    
    def apply_voucher(self, voucher):
        if not voucher.is_valid:
            return False
        
        discount = voucher.calculate_discount(self.subtotal)
        if discount > 0:
            self.voucher = voucher
            self.voucher_discount = discount
            self.total_price = self.get_total()
            self.save()
            voucher.use_voucher()
            return True
        return False

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    
    class Meta:
        unique_together = ['order', 'product']
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name} in Order {self.order.order_number}"
    
    @property
    def total_price(self):
        return self.price * self.quantity

class ShippingAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    address_line1 = models.CharField(max_length=200)
    address_line2 = models.CharField(max_length=200, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_default', '-created_at']
        verbose_name_plural = 'Shipping addresses'
    
    def __str__(self):
        return f"{self.name}, {self.city}"
    
    def save(self, *args, **kwargs):
        if self.is_default:
            ShippingAddress.objects.filter(user=self.user).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

class CreditCard(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    card_number = models.CharField(max_length=16)
    card_holder = models.CharField(max_length=100)
    expiry_month = models.PositiveSmallIntegerField()
    expiry_year = models.PositiveSmallIntegerField()
    cvv = models.CharField(max_length=4, blank=True, null=True)  # Not stored in database for security
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_default', '-created_at']
    
    def __str__(self):
        masked_number = f"**** **** **** {self.card_number[-4:]}"
        return f"{masked_number} - {self.card_holder}"
    
    def save(self, *args, **kwargs):
        # Don't store the CVV
        self.cvv = None
        
        # Handle default card
        if self.is_default:
            CreditCard.objects.filter(user=self.user).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    @property
    def masked_number(self):
        return f"**** **** **** {self.card_number[-4:]}"
    
    @property
    def expiry_date(self):
        return f"{self.expiry_month:02d}/{str(self.expiry_year)[2:]}"

class PromoBanner(models.Model):
    LINK_CHOICES = (
        ('product_list', 'All Products'),
        ('cart', 'Shopping Cart'),
        ('profile', 'User Profile'),
        ('custom', 'Custom URL'),
    )
    TEXT_COLOR_CHOICES = (
        ('text-white', 'White'),
        ('text-dark', 'Dark'),
        ('text-primary', 'Blue'),
        ('text-success', 'Green'),
        ('text-danger', 'Red'),
        ('text-warning', 'Yellow'),
    )
    BUTTON_STYLE_CHOICES = (
        ('btn-primary', 'Blue'),
        ('btn-success', 'Green'),
        ('btn-danger', 'Red'),
        ('btn-warning', 'Yellow'),
        ('btn-info', 'Light Blue'),
        ('btn-dark', 'Dark'),
        ('btn-light', 'Light'),
        ('btn-outline-primary', 'Outlined Blue'),
        ('btn-outline-success', 'Outlined Green'),
        ('btn-outline-danger', 'Outlined Red'),
    )
    CAPTION_POSITION_CHOICES = (
        ('center', 'Center'),
        ('left', 'Left'),
        ('right', 'Right'),
    )
    title = models.CharField(max_length=100)
    subtitle = models.CharField(max_length=200)
    image = models.ImageField(upload_to='banners/')
    button_text = models.CharField(max_length=50, default='Shop Now')
    link_type = models.CharField(max_length=20, choices=LINK_CHOICES, default='product_list')
    button_link = models.CharField(max_length=200, blank=True)
    active = models.BooleanField(default=True)
    start_date = models.DateField(null=True, blank=True, help_text="Leave blank for no start restriction")
    end_date = models.DateField(null=True, blank=True, help_text="Leave blank for no end restriction")
    text_color = models.CharField(max_length=20, choices=TEXT_COLOR_CHOICES, default='text-white')
    button_style = models.CharField(max_length=20, choices=BUTTON_STYLE_CHOICES, default='btn-primary')
    caption_position = models.CharField(max_length=10, choices=CAPTION_POSITION_CHOICES, default='center')
    overlay_opacity = models.FloatField(default=0.4, help_text="Background opacity for caption (0-1)")
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order', 'created_at']
    
    def __str__(self):
        return self.title
    
    def get_button_url(self):
        if self.link_type == 'custom':
            return self.button_link
        return reverse(self.link_type)
    
    def get_status(self):
        today = timezone.now().date()
        if not self.active:
            return 'inactive'
        if self.start_date and self.start_date > today:
            return 'upcoming'
        if self.end_date and self.end_date < today:
            return 'expired'
        return 'active'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.image:
            img = Image.open(self.image.path)
            if img.height > 800 or img.width > 1600:
                output_size = (1600, 800)
                img.thumbnail(output_size, Image.Resampling.LANCZOS)
                img.save(self.image.path, quality=85)

class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('order', 'Order'),
        ('payment', 'Payment'),
        ('system', 'System'),
        ('promo', 'Promotion'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=100, default="Notification")
    message = models.CharField(max_length=255)
    link = models.CharField(max_length=255, blank=True, null=True)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='system')
    reference_id = models.IntegerField(blank=True, null=True, help_text="ID of the referenced object (e.g., order ID)")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Notification for {self.user.username}: {self.title}"
        
    @classmethod
    def delete_old_read_notifications(cls):
        """Delete notifications that are read and older than 1 year"""
        one_year_ago = timezone.now() - timezone.timedelta(days=365)
        cls.objects.filter(is_read=True, created_at__lt=one_year_ago).delete()

class Voucher(models.Model):
    DISCOUNT_TYPE_CHOICES = (
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    )
    
    VOUCHER_TYPE_CHOICES = (
        ('general', 'General Voucher'),
        ('dedicated', 'User-Specific Voucher'),
    )
    
    code = models.CharField(max_length=20, unique=True)
    voucher_type = models.CharField(max_length=10, choices=VOUCHER_TYPE_CHOICES, default='general')
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES, default='percentage')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    max_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, 
                                      help_text="Maximum discount amount for percentage discounts")
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    min_purchase_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    usage_limit = models.PositiveIntegerField(default=1, help_text="Number of times this voucher can be used")
    used_count = models.PositiveIntegerField(default=0, help_text="Number of times this voucher has been used")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-valid_from']
    
    def __str__(self):
        return f"{self.code} - {self.get_discount_type_display()} {self.discount_value}"
    
    @property
    def is_valid(self):
        now = timezone.now()
        return (
            self.is_active and 
            self.valid_from <= now <= self.valid_to and
            (self.usage_limit is None or self.used_count < self.usage_limit)
        )
    
    def calculate_discount(self, total_amount):
        if not self.is_valid:
            return 0
        
        if total_amount < self.min_purchase_amount:
            return 0
        
        if self.discount_type == 'percentage':
            discount = total_amount * (self.discount_value / 100)
            if self.max_discount is not None and discount > self.max_discount:
                discount = self.max_discount
        else:  # fixed amount
            discount = self.discount_value
            if discount > total_amount:
                discount = total_amount
                
        return discount
    
    def use_voucher(self):
        logger.info(f"[VOUCHER_USE] Incrementing used_count for Voucher {self.id} ('{self.code}'). Current count: {self.used_count}")
        self.used_count += 1
        if self.used_count >= self.usage_limit:
            logger.warning(f"[VOUCHER_USE] Voucher {self.id} reached usage limit ({self.used_count}/{self.usage_limit}). Deactivating.")
            self.is_active = False
        try:
            self.save(update_fields=['used_count', 'is_active'])
            logger.info(f"[VOUCHER_USE] Successfully saved Voucher {self.id}. New count: {self.used_count}, Active: {self.is_active}")
        except Exception as e:
            logger.error(f"[VOUCHER_USE] Error saving Voucher {self.id} after incrementing count: {e}")
            # Consider how to handle this error - maybe raise it?

class UserVoucher(models.Model):
    """Model for user-specific vouchers"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_vouchers')
    voucher = models.ForeignKey(Voucher, on_delete=models.CASCADE, related_name='user_vouchers')
    is_used = models.BooleanField(default=False)
    message = models.CharField(max_length=255, blank=True, null=True, help_text="Personalized message to send to the user")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'voucher']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.voucher.code} for {self.user.username}"
    
    @property
    def is_valid(self):
        return self.voucher.is_valid and not self.is_used
    
    def use_voucher(self):
        logger.info(f"[USER_VOUCHER_USE] Marking UserVoucher {self.id} (User: {self.user.id}, Voucher: {self.voucher.id}) as used. Current status: {self.is_used}")
        self.is_used = True
        try:
            self.save(update_fields=['is_used'])
            logger.info(f"[USER_VOUCHER_USE] Successfully saved UserVoucher {self.id} as used.")
        except Exception as e:
            logger.error(f"[USER_VOUCHER_USE] Error saving UserVoucher {self.id} after marking as used: {e}")
            # Consider raising the error or implementing retry logic
            return # Stop here if save fails
            
        # Call the main voucher usage method *after* successfully marking UserVoucher
        try:
            self.voucher.use_voucher()
        except Exception as e:
             logger.error(f"[USER_VOUCHER_USE] Error calling Voucher.use_voucher() for Voucher {self.voucher.id} from UserVoucher {self.id}: {e}")
             # Potential issue: UserVoucher is marked used, but Voucher count failed.
             # You might need a transaction here to ensure atomicity.

class Package(models.Model):
    RATING_CHOICES = [(i, i) for i in range(1, 6)]
    
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField()
    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    discounted_price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='packages/', blank=True, null=True)
    category = models.ForeignKey(Category, related_name='packages', on_delete=models.CASCADE)
    minimum_purchase_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Minimum amount customers must purchase when customizing")
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_ratings = models.PositiveIntegerField(default=0)
    sold_count = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('package_detail', kwargs={'slug': self.slug})
    
    def update_rating(self):
        """Update the average rating and total ratings count for this package"""
        ratings = self.ratings.all()
        if ratings.exists():
            total = sum(r.rating for r in ratings)
            count = ratings.count()
            self.average_rating = round(total / count, 2)
            self.total_ratings = count
            self.save(update_fields=['average_rating', 'total_ratings'])
        else:
            self.average_rating = 0
            self.total_ratings = 0
            self.save(update_fields=['average_rating', 'total_ratings'])
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
        if self.image:
            try:
                img = Image.open(self.image.path)
                if img.height > 800 or img.width > 800:
                    output_size = (800, 800)
                    img.thumbnail(output_size, Image.Resampling.LANCZOS)
                    img.save(self.image.path, quality=85)
            except (IOError, OSError) as e:
                logger = logging.getLogger(__name__)
                logger.error(f"Error processing image for package {self.name}: {str(e)}")

    @property
    def discount_amount(self):
        if self.original_price > self.discounted_price:
            return self.original_price - self.discounted_price
        return 0
    
    @property
    def discount_percent(self):
        if self.original_price > self.discounted_price:
            return round((self.original_price - self.discounted_price) / self.original_price * 100)
        return 0
    
    @property
    def final_price(self):
        return self.discounted_price
    
    def total_products_price(self):
        """Calculate the total price of all products in this package at their individual prices"""
        return sum(item.product.price * item.quantity for item in self.package_products.all())
        
    @property
    def is_available(self):
        """Check if all products in the package have enough stock"""
        for pp in self.package_products.all():
            if pp.product.stock < pp.quantity:
                return False
        return True
    
    def get_unavailable_items(self):
        """Return a list of unavailable items in the package"""
        unavailable = []
        for pp in self.package_products.all():
            if pp.product.stock < pp.quantity:
                unavailable.append(pp.product.name)
        return unavailable

class PackageProduct(models.Model):
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name='package_products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='in_packages')
    quantity = models.PositiveIntegerField(default=1)
    is_required = models.BooleanField(default=False, help_text="If true, this product cannot be removed from the package")
    
    class Meta:
        unique_together = ['package', 'product']
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name} in {self.package.name}"
    
    @property
    def total_price(self):
        return self.product.price * self.quantity

class PackageRating(models.Model):
    RATING_CHOICES = [(i, i) for i in range(1, 6)]
    
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='package_ratings')
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, default=5)
    feedback = models.TextField(help_text="Share your experience with this package")
    staff_reviewed = models.BooleanField(default=False, help_text="Has this rating been reviewed by staff")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['package', 'user']
    
    def __str__(self):
        return f"{self.user.username}'s {self.rating}-star rating for {self.package.name}"
    
    def save(self, *args, **kwargs):
        # Check if the user has purchased this package
        from .models import OrderPackage
        has_purchased = OrderPackage.objects.filter(
            order__user=self.user,
            package=self.package,
            order__status__in=['processing', 'shipped', 'delivered']
        ).exists()
        
        # Skip the purchase check temporarily
        # if not has_purchased:
        #     pass
            
        # Save the rating
        super().save(*args, **kwargs)
        
        # Update the package's average rating
        self.package.update_rating()

class PackageComment(models.Model):
    STATUS_CHOICES = (
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    )
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    is_private = models.BooleanField(default=False)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_package_comments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f'Comment by {self.user.username} on {self.package.name}'

class CustomizedPackage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    original_package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name='customizations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Customized {self.original_package.name} by {self.user.username}"
    
    @property
    def total_price(self):
        return sum(item.total_price for item in self.items.all())
    
    def meets_minimum_requirement(self):
        """Check if the customized package meets the minimum purchase amount"""
        return self.total_price >= self.original_package.minimum_purchase_amount

class CustomizedPackageItem(models.Model):
    customized_package = models.ForeignKey(CustomizedPackage, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    
    class Meta:
        unique_together = ['customized_package', 'product']
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name} in customized package"
    
    @property
    def total_price(self):
        return self.product.price * self.quantity

class OrderPackage(models.Model):
    order = models.ForeignKey(Order, related_name='packages', on_delete=models.CASCADE)
    package = models.ForeignKey(Package, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Package {self.package.name} in Order {self.order.order_number}"

class OrderPackageItem(models.Model):
    order_package = models.ForeignKey(OrderPackage, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    
    class Meta:
        unique_together = ['order_package', 'product']
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name} in order package {self.order_package.id}"
    
    @property
    def total_price(self):
        return self.price * self.quantity

class CartPackage(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='packages')
    package = models.ForeignKey(Package, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.package.name} in Cart {self.cart.id}"
    
    @property
    def total_price(self):
        return self.package.discounted_price
        
    def is_available(self):
        """Check if all package items are in stock"""
        for item in self.items.all():
            if item.product.stock < item.quantity:
                return False
        return True
    
    def get_unavailable_items(self):
        """Return a list of unavailable items in the package"""
        unavailable = []
        for item in self.items.all():
            if item.product.stock < item.quantity:
                unavailable.append(item.product.name)
        return unavailable

class CartPackageItem(models.Model):
    cart_package = models.ForeignKey(CartPackage, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    
    class Meta:
        unique_together = ['cart_package', 'product']
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name} in cart package {self.cart_package.id}"
    
    @property
    def total_price(self):
        return self.product.price * self.quantity