from django.core.management.base import BaseCommand
from django.utils import timezone
from livechat.models import ChatSession
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Cleans up expired chat sessions that are marked for auto-deletion'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        now = timezone.now()
        
        # Get chats to delete
        expired_chats = ChatSession.objects.filter(
            auto_delete=True,
            delete_after__lt=now,
            status='closed'
        )
        
        count = expired_chats.count()
        
        if dry_run:
            self.stdout.write(f"Would delete {count} expired chat sessions")
            for chat in expired_chats:
                ended_days_ago = (now - chat.ended_at).days
                self.stdout.write(f"  - Chat {chat.id} ended {ended_days_ago} days ago")
        else:
            logger.info(f"Deleting {count} expired chat sessions")
            deleted = expired_chats.delete()
            self.stdout.write(
                self.style.SUCCESS(f'Successfully deleted {count} expired chat sessions')
            )
            
        # Also check for active but abandoned chats
        abandoned_time = now - timezone.timedelta(days=7)
        abandoned_chats = ChatSession.objects.filter(
            is_active=True,
            started_at__lt=abandoned_time,
            status__in=['waiting', 'active']
        )
        
        abandoned_count = abandoned_chats.count()
        
        if dry_run:
            self.stdout.write(f"Would close {abandoned_count} abandoned chat sessions")
            for chat in abandoned_chats:
                days_old = (now - chat.started_at).days
                self.stdout.write(f"  - Chat {chat.id} started {days_old} days ago and is still {chat.status}")
        else:
            for chat in abandoned_chats:
                chat.close(auto_delete=True)
                logger.info(f"Closed abandoned chat {chat.id}")
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully closed {abandoned_count} abandoned chat sessions')
            ) 