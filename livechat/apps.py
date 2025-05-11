from django.apps import AppConfig
from django.db.models.signals import post_migrate
import threading
import time
import logging

logger = logging.getLogger(__name__)


class LivechatConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'livechat'
    
    def ready(self):
        # Import the models here to avoid circular imports
        from .models import ChatSession
        
        # Start the cleanup thread
        if not getattr(self, 'cleanup_thread_started', False):
            self.cleanup_thread_started = True
            
            # Function to perform the cleanup
            def cleanup_function():
                # Sleep for 10 seconds to let the app fully initialize
                time.sleep(10)
                
                while True:
                    try:
                        # Delete expired chats
                        deleted_count = ChatSession.delete_expired_chats()
                        if deleted_count > 0:
                            logger.info(f"Cleaned up {deleted_count} expired chat sessions")
                        
                        # Sleep for 1 hour before the next cleanup
                        time.sleep(3600)
                    except Exception as e:
                        logger.error(f"Error in chat cleanup thread: {e}")
                        # Sleep for 5 minutes before retrying on error
                        time.sleep(300)
            
            # Start a daemon thread for cleanup
            cleanup_thread = threading.Thread(target=cleanup_function, daemon=True)
            cleanup_thread.start()
            logger.info("Chat cleanup thread started")
