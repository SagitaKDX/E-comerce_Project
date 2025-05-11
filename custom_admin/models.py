from django.db import models
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

# Create your models here.

class FAQ(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    content = models.TextField(help_text="You can use Markdown or LaTeX for formatting")
    order = models.PositiveIntegerField(default=0, help_text="Order in which this FAQ appears")
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order', 'title']
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class AdminConfiguration(models.Model):
    site_name = models.CharField(max_length=100, default="E-Commerce Admin")
    site_logo = models.ImageField(upload_to='admin/logos/', null=True, blank=True)
    primary_color = models.CharField(max_length=20, default="#3498db")
    secondary_color = models.CharField(max_length=20, default="#2ecc71")
    enable_dark_mode = models.BooleanField(default=False)
    
    def __str__(self):
        return self.site_name
    
    class Meta:
        verbose_name = "Admin Configuration"
        verbose_name_plural = "Admin Configurations"


class LoyaltyTier(models.Model):
    name = models.CharField(max_length=50)
    slug = models.SlugField(unique=True, blank=True)
    minimum_spend = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    color_class = models.CharField(max_length=20, default="primary", 
                               help_text="Bootstrap color class (primary, secondary, success, etc.)")
    icon = models.CharField(max_length=50, default="fas fa-medal")
    badge_color = models.CharField(max_length=20, default="#3498db")
    tier_level = models.PositiveIntegerField(default=1, help_text="Used for sorting tiers")
    benefits = models.TextField(blank=True, help_text="Comma-separated list of benefits")
    tier_benefits = models.TextField(blank=True, help_text="List benefits users receive at this tier")
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00,
                                           help_text="Percentage discount for this tier (0-100)")
    voucher_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, 
                                       help_text="Amount of voucher issued when customer reaches this tier")
    is_active = models.BooleanField(default=True, help_text="Only active tiers are assigned to customers")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['minimum_spend']
        verbose_name = "Loyalty Tier"
        verbose_name_plural = "Loyalty Tiers"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} (${self.minimum_spend}+)"


class CustomerLoyalty(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='loyalty')
    current_tier = models.ForeignKey(LoyaltyTier, on_delete=models.SET_NULL, null=True, blank=True)
    total_spend = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    points = models.IntegerField(default=0)
    anniversary_date = models.DateField(null=True, blank=True)
    last_anniversary_reward = models.DateField(null=True, blank=True)
    tier_updated_at = models.DateTimeField(null=True, blank=True)
    
    def update_tier(self):
        """Update user's loyalty tier based on their total spend"""
        eligible_tier = LoyaltyTier.objects.filter(
            minimum_spend__lte=self.total_spend,
            is_active=True
        ).order_by('-minimum_spend').first()
        
        if eligible_tier and (not self.current_tier or self.current_tier.id != eligible_tier.id):
            previous_tier = self.current_tier
            self.current_tier = eligible_tier
            self.tier_updated_at = timezone.now()
            self.save()
            return True, previous_tier
        return False, None
    
    def check_anniversary(self):
        """Check if user has reached their anniversary and deserves a reward"""
        if not self.anniversary_date:
            return False
        
        today = timezone.now().date()
        anniversary_this_year = self.anniversary_date.replace(year=today.year)
        
        # If today is on or after anniversary date for this year
        # and we haven't given a reward already for this year
        if (today >= anniversary_this_year and 
            (not self.last_anniversary_reward or 
             self.last_anniversary_reward.year < today.year)):
            self.last_anniversary_reward = today
            self.save()
            return True
            
        return False
    
    def __str__(self):
        tier_name = self.current_tier.name if self.current_tier else "No Tier"
        return f"{self.user.username} - {tier_name} (${self.total_spend})"


class LoyaltyVoucher(models.Model):
    VOUCHER_TYPES = (
        ('tier', 'Tier Upgrade'),
        ('anniversary', 'Anniversary'),
        ('manual', 'Manually Created'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='loyalty_vouchers')
    voucher_type = models.CharField(max_length=20, choices=VOUCHER_TYPES)
    tier = models.ForeignKey(LoyaltyTier, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    code = models.CharField(max_length=20, unique=True)
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    @property
    def is_expired(self):
        return timezone.now() > self.valid_until
    
    def use_voucher(self):
        if not self.is_used and self.valid_until > timezone.now():
            self.is_used = True
            self.used_at = timezone.now()
            self.save()
            return True
        return False
    
    def __str__(self):
        return f"{self.code} - {self.user.username} - ${self.amount}"
