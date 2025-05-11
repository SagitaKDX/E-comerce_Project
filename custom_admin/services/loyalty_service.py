import uuid
import json
import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum
from django.conf import settings
from django.db import transaction
from django.contrib.auth import get_user_model

from custom_admin.models import CustomerLoyalty, LoyaltyTier, LoyaltyVoucher

logger = logging.getLogger(__name__)
User = get_user_model()

def update_customer_loyalty(user, order_total):
    """
    Update a customer's loyalty status when an order is placed or completed.
    
    Args:
        user: The User object of the customer
        order_total: The total amount of the completed order
        
    Returns:
        tuple: (tier_changed, voucher_created, new_tier)
    """
    loyalty, created = CustomerLoyalty.objects.get_or_create(user=user)
    
    # Update total spend, of each user
    loyalty.total_spend += order_total
    
    if created or not loyalty.anniversary_date:
        loyalty.anniversary_date = user.date_joined.date()
    
    
    loyalty.save()
    
    tier_changed, previous_tier = loyalty.update_tier()
    
    voucher_created = False
    if tier_changed and loyalty.current_tier:
        voucher_created = _create_tier_upgrade_voucher(user, loyalty.current_tier, previous_tier)
    
    return tier_changed, voucher_created, loyalty.current_tier

def check_and_create_anniversary_vouchers():
    """
    Check all users for account anniversaries and create vouchers if needed
    Returns the number of vouchers created
    """
    today = timezone.now().date()
    vouchers_created = 0
    
    loyalty_profiles = CustomerLoyalty.objects.select_related('user').filter(
        anniversary_date__isnull=False
    )
    
    for loyalty in loyalty_profiles:
        try:
            if _is_anniversary(loyalty.anniversary_date, today):
                if not loyalty.last_anniversary_reward or loyalty.last_anniversary_reward.year < today.year:
                    if _create_anniversary_voucher(loyalty.user):
                        vouchers_created += 1
                        
                        loyalty.last_anniversary_reward = today
                        loyalty.save(update_fields=['last_anniversary_reward'])
        except Exception as e:
            logger.error(f"Error checking anniversary for user {loyalty.user.id}: {str(e)}")
    
    logger.info(f"Anniversary check complete. Created {vouchers_created} vouchers.")
    return vouchers_created

def _is_anniversary(anniversary_date, today):
    if not anniversary_date:
        return False
    
    return (anniversary_date.month == today.month and 
            anniversary_date.day == today.day)

def recalculate_all_loyalty_tiers():
    updated_count = 0
    users_processed = 0
    
    loyalty_profiles = CustomerLoyalty.objects.select_related('user', 'current_tier').all()
    
    active_tiers = LoyaltyTier.objects.filter(is_active=True).order_by('-minimum_spend')
    
    if not active_tiers.exists():
        logger.warning("No active loyalty tiers found during recalculation")
        return 0
    
    for loyalty in loyalty_profiles:
        try:
            users_processed += 1
            
            eligible_tier = None
            for tier in active_tiers:
                if loyalty.total_spend >= tier.minimum_spend:
                    eligible_tier = tier
                    break
            
            if (eligible_tier and not loyalty.current_tier) or \
               (eligible_tier and loyalty.current_tier and eligible_tier.id != loyalty.current_tier.id) or \
               (not eligible_tier and loyalty.current_tier):
                
                previous_tier = loyalty.current_tier
                loyalty.current_tier = eligible_tier
                loyalty.tier_updated_at = timezone.now()
                loyalty.save()
                
                updated_count += 1
                
                if previous_tier and eligible_tier:
                    logger.info(f"User {loyalty.user.username} moved from {previous_tier.name} to {eligible_tier.name}")
                elif previous_tier:
                    logger.info(f"User {loyalty.user.username} removed from {previous_tier.name} tier")
                elif eligible_tier:
                    logger.info(f"User {loyalty.user.username} assigned to {eligible_tier.name} tier")
                
                if eligible_tier and (not previous_tier or eligible_tier.minimum_spend > previous_tier.minimum_spend):
                    _create_tier_upgrade_voucher(loyalty.user, eligible_tier)
        
        except Exception as e:
            logger.error(f"Error processing loyalty tier for user {loyalty.user.id}: {str(e)}")
    
    logger.info(f"Loyalty tier recalculation complete. Processed {users_processed} users, updated {updated_count} tiers.")
    return updated_count

def _create_tier_upgrade_voucher(user, new_tier, previous_tier):
    """
    Create a voucher when a user reaches a new tier
    
    Args:
        user: The User object
        new_tier: The new LoyaltyTier the user has reached
        previous_tier: The user's previous LoyaltyTier or None
        
    Returns:
        bool: Whether a voucher was created
    """
    if not new_tier.voucher_amount or new_tier.voucher_amount <= 0:
        return False
    
    code = f"TIER-{user.id}-{uuid.uuid4().hex[:8].upper()}"
    
    valid_until = timezone.now() + timedelta(days=90)
    
    LoyaltyVoucher.objects.create(
        user=user,
        voucher_type='tier',
        tier=new_tier,
        amount=new_tier.voucher_amount,
        code=code,
        valid_until=valid_until
    )
    
    logger.info(f"Created tier upgrade voucher {code} for {user.username} - {new_tier.name}")
    return True

def _create_anniversary_voucher(user):
    """Create an anniversary voucher for a user"""
    try:
        amount = 10.00
        
        try:
            loyalty = CustomerLoyalty.objects.select_related('current_tier').get(user=user)
            if loyalty.current_tier and loyalty.current_tier.voucher_amount:
                amount = loyalty.current_tier.voucher_amount
        except CustomerLoyalty.DoesNotExist:
            pass
        
        code = f"ANNIV_{uuid.uuid4().hex[:8].upper()}"
        
        expiry_date = timezone.now() + timezone.timedelta(days=30)
        
        LoyaltyVoucher.objects.create(
            user=user,
            voucher_type='anniversary',
            amount=amount,
            code=code,
            valid_until=expiry_date,
            is_used=False
        )
        
        logger.info(f"Created anniversary voucher {code} for user {user.username}")
        return True
    except Exception as e:
        logger.error(f"Error creating anniversary voucher: {str(e)}")
    
    return False

def _load_loyalty_settings():
    """Load loyalty settings from JSON file"""
    try:
        with open('loyalty_settings.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            'anniversary_vouchers': {
                'active': True,
                'amount': 10.00,
                'valid_days': 30
            }
        } 