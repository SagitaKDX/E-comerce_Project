from django.contrib import admin
from .models import AdminConfiguration, LoyaltyTier, CustomerLoyalty, LoyaltyVoucher

@admin.register(AdminConfiguration)
class AdminConfigurationAdmin(admin.ModelAdmin):
    list_display = ('site_name', 'enable_dark_mode')

@admin.register(LoyaltyTier)
class LoyaltyTierAdmin(admin.ModelAdmin):
    list_display = ('name', 'minimum_spend', 'tier_level', 'voucher_amount')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)
    ordering = ('minimum_spend',)

@admin.register(CustomerLoyalty)
class CustomerLoyaltyAdmin(admin.ModelAdmin):
    list_display = ('user', 'current_tier', 'total_spend', 'points')
    search_fields = ('user__username', 'user__email')
    list_filter = ('current_tier',)
    readonly_fields = ('tier_updated_at',)

@admin.register(LoyaltyVoucher)
class LoyaltyVoucherAdmin(admin.ModelAdmin):
    list_display = ('code', 'user', 'voucher_type', 'amount', 'is_used', 'valid_until')
    search_fields = ('code', 'user__username', 'user__email')
    list_filter = ('voucher_type', 'is_used', 'tier')
    readonly_fields = ('used_at', 'created_at')
