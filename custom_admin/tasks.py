from celery import shared_task
import logging
from .services.loyalty_service import check_and_create_anniversary_vouchers, recalculate_all_loyalty_tiers

logger = logging.getLogger(__name__)

@shared_task
def check_anniversary_vouchers():
    """
    Check all users for anniversaries and create vouchers if needed.
    Runs daily via Celery Beat schedule.
    """
    try:
        count = check_and_create_anniversary_vouchers()
        return f"Created {count} anniversary vouchers"
    except Exception as e:
        logger.error(f"Error checking anniversary vouchers: {str(e)}")
        return f"Error checking anniversary vouchers: {str(e)}"

@shared_task
def recalculate_loyalty_tiers():
    """
    Recalculate loyalty tiers for all users.
    Use this task after changing tier thresholds or for initial data migration.
    """
    try:
        count = recalculate_all_loyalty_tiers()
        return f"Updated {count} users' loyalty tiers"
    except Exception as e:
        logger.error(f"Error recalculating loyalty tiers: {str(e)}")
        return f"Error recalculating loyalty tiers: {str(e)}" 