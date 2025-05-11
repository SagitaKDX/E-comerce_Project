from django.conf import settings
from django.urls import reverse

def floating_chat_processor(request):
    """
    Context processor to include floating chat widget in all templates
    """
    include_floating_chat = True
    
    # Don't include the floating chat on admin pages
    if request.path.startswith('/admin/') or request.path.startswith('/crm/'):
        include_floating_chat = False
    
    # Don't include the floating chat on chat-related pages themselves
    if request.path.startswith('/livechat/chat/'):
        include_floating_chat = False
    
    # Don't include floating chat for CRM users in agent dashboard
    if hasattr(request.user, 'profile') and request.user.profile.is_crm_user:
        if request.path.startswith('/livechat/agent/'):
            include_floating_chat = False
    
    return {
        'include_floating_chat': include_floating_chat,
        'floating_chat_url': reverse('livechat:floating_chat')
    } 