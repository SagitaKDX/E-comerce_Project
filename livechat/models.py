from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
from datetime import timedelta

class ChatSession(models.Model):
    """Model to track active chat sessions"""
    STATUS_CHOICES = (
        ('waiting', 'Waiting for support'),
        ('active', 'Active - Assigned to agent'),
        ('closed', 'Closed'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='chat_sessions')
    agent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_chats')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    subject = models.CharField(max_length=255, default="Support Chat")
    user_email = models.EmailField(blank=True, null=True)  # Store email for non-authenticated users
    session_key = models.CharField(max_length=100, blank=True, null=True)  # Browser session key
    page_viewed = models.BooleanField(default=False)  # Track if chat page was viewed
    auto_delete = models.BooleanField(default=True)  # Whether to delete chat after retention period
    delete_after = models.DateTimeField(null=True, blank=True)  # When to delete the chat
    
    # Default retention period in days
    RETENTION_PERIOD = 30
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        if self.user:
            return f"Chat with {self.user.username} - {self.get_status_display()}"
        return f"Chat {self.id} - {self.get_status_display()}"
    
    def assign_to_agent(self, agent):
        """Assign this chat to a support agent"""
        self.agent = agent
        self.status = 'active'
        self.save()
    
    def close(self, auto_delete=True):
        """Close this chat session and set auto-deletion if enabled"""
        self.status = 'closed'
        self.is_active = False
        self.ended_at = timezone.now()
        
        if auto_delete:
            self.auto_delete = True
            self.delete_after = timezone.now() + timedelta(days=self.RETENTION_PERIOD)
        
        self.save()
    
    @property
    def duration(self):
        """Calculate the duration of the chat session"""
        if not self.ended_at:
            return timezone.now() - self.started_at
        return self.ended_at - self.started_at
    
    @classmethod
    def delete_expired_chats(cls):
        """Delete chats that are past their retention period"""
        now = timezone.now()
        expired_chats = cls.objects.filter(
            auto_delete=True,
            delete_after__lt=now,
            status='closed'
        )
        
        count = expired_chats.count()
        expired_chats.delete()
        return count

class ChatMessage(models.Model):
    """Model to store chat messages"""
    TYPE_CHOICES = (
        ('text', 'Text Message'),
        ('system', 'System Message'),
        ('image', 'Image')
    )
    
    chat_session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_messages')
    sender_name = models.CharField(max_length=100, blank=True)  # For display purposes
    is_agent = models.BooleanField(default=False)  # To differentiate between user and agent messages
    content = models.TextField()
    message_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='text')
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f"Message from {self.sender_name} at {self.timestamp.strftime('%H:%M:%S')}"
    
    def save(self, *args, **kwargs):
        # Set sender_name if not provided
        if not self.sender_name:
            if self.sender:
                self.sender_name = self.sender.get_full_name() or self.sender.username
            elif not self.is_agent and self.chat_session.user_email:
                # For anonymous users, use their email as sender name
                self.sender_name = self.chat_session.user_email
            elif not self.is_agent:
                self.sender_name = "Guest User"
            else:
                self.sender_name = "Support Agent"
        super().save(*args, **kwargs)
