from .models import Category, Cart, Notification

def categories(request):
    """
    Context processor to add categories to all templates
    """
    return {
        'categories': Category.objects.all()
    }

def cart_processor(request):
    """
    Context processor to add cart to all templates
    """
    cart = None
    cart_items_count = 0
    cart_total_quantity = 0
    
    try:
        if request.user.is_authenticated:
            try:
                cart = Cart.objects.get(user=request.user)
                cart_items_count = cart.total_items
                cart_total_quantity = cart.total_quantity
            except Cart.DoesNotExist:
                pass
        elif request.session.session_key:
            try:
                cart = Cart.objects.get(session_id=request.session.session_key)
                cart_items_count = cart.total_items
                cart_total_quantity = cart.total_quantity
            except Cart.DoesNotExist:
                pass
    except Exception as e:
        # Handle any database errors
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in cart processor: {str(e)}")
    
    return {
        'cart': cart,
        'cart_items_count': cart_items_count,
        'cart_total_quantity': cart_total_quantity
    }

def notifications_processor(request):
    """
    Context processor to add notifications to all templates
    """
    notifications = []
    unread_count = 0
    
    if request.user.is_authenticated:
        try:
            # Get the 5 most recent notifications
            notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
            
            # Get the total unread count
            unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
            
            # Auto cleanup old notifications
            Notification.delete_old_read_notifications()
        except Exception:
            # Handle the case where the table might not exist yet
            pass
    
    return {
        'header_notifications': notifications,
        'unread_notifications_count': unread_count
    }
