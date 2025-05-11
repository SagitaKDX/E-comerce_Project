import logging

logger = logging.getLogger('django.channels')

class ChatXFrameOptionsMiddleware:
    """
    Middleware to remove X-Frame-Options header for chat-related views
    This allows the chat to be embedded in iframes
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        logger.info("ChatXFrameOptionsMiddleware initialized")
        
    def __call__(self, request):
        response = self.get_response(request)
        
        # Check if this is a chat-related URL
        is_chat_url = '/livechat/' in request.path
        is_embed_url = 'embed' in request.path or request.GET.get('embedded')
        is_chat_room = '/chat/' in request.path
        
        if is_chat_url and (is_embed_url or is_chat_room):
            logger.debug(f"Removing X-Frame-Options for path: {request.path}")
            # Remove X-Frame-Options header to allow embedding
            if 'X-Frame-Options' in response:
                del response['X-Frame-Options']
            
        return response 