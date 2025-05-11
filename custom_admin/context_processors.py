from django.utils import timezone
from datetime import timedelta
from store.models import ProductRating, PackageRating

def crm_context(request):
    """
    Add CRM-specific context to all templates in the CRM section
    """
    context = {}
    
    # Only add these variables if we're in the CRM section
    if request.path.startswith('/crm/') and request.user.is_authenticated:
        # Get count of new ratings in the last 24 hours
        one_day_ago = timezone.now() - timedelta(days=1)
        new_product_ratings_count = ProductRating.objects.filter(
            created_at__gte=one_day_ago
        ).count()
        
        new_package_ratings_count = PackageRating.objects.filter(
            created_at__gte=one_day_ago
        ).count()
        
        context['new_ratings_count'] = new_product_ratings_count + new_package_ratings_count
    
    return context 