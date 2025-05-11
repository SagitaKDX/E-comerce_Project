import json
import logging
import traceback
import uuid
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.utils import timezone
from .models import ChatSession, ChatMessage
from channels.layers import get_channel_layer

# Compatibility fix - manually define async_to_sync if needed
try:
    from channels.sync import async_to_sync
except ImportError:
    # Fallback for channels 4.0.0
    from asgiref.sync import async_to_sync

logger = logging.getLogger('django.channels')

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        self.room_group_name = f'chat_{self.chat_id}'
        
        logger.debug(f"WebSocket connection attempt for chat: {self.chat_id}")
        logger.debug(f"Connection scope: {self.scope}")
        
        try:
            # Join the room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            # Accept the connection
            await self.accept()
            logger.debug(f"WebSocket connection accepted for chat: {self.chat_id}")
            
            # Check if session exists and update status
            session_exists = await self.check_session_exists()
            if not session_exists:
                logger.info(f"Chat session not found - creating new one: {self.chat_id}")
                # Create a new session instead of rejecting the connection
                session_created = await self.create_chat_session()
                if not session_created:
                    logger.warning(f"Failed to create chat session: {self.chat_id}")
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'Failed to create chat session.'
                    }))
                    await self.close()
                    return
                else:
                    logger.info(f"New chat session created successfully: {self.chat_id}")
                
            # Send system message when connected
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'system_message',
                    'message': 'Connected to chat support'
                }
            )
            logger.debug(f"System message sent for chat: {self.chat_id}")
        except Exception as e:
            logger.error(f"Error in WebSocket connect: {str(e)}")
            logger.error(traceback.format_exc())
            # Try to send an error message and close
            try:
                await self.accept()
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Connection error: Unable to establish WebSocket connection.'
                }))
                await self.close()
            except:
                pass
    
    @database_sync_to_async
    def create_chat_session(self):
        """Create a new chat session if one doesn't exist"""
        try:
            # Check if it already exists first
            try:
                session = ChatSession.objects.get(id=self.chat_id)
                if not session.is_active:
                    session.is_active = True
                    session.save(update_fields=['is_active'])
                    logger.info(f"Reactivated existing chat session: {self.chat_id}")
                return True
            except ChatSession.DoesNotExist:
                # Create a new session with the provided ID
                session = ChatSession.objects.create(
                    id=self.chat_id,
                    status='waiting',
                    is_active=True,
                    subject='General Inquiry',  # Default subject
                    created_at=timezone.now()
                )
                logger.info(f"Created new chat session with ID: {self.chat_id}")
                return True
        except Exception as e:
            logger.error(f"Error creating chat session: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    async def disconnect(self, close_code):
        logger.debug(f"WebSocket disconnecting, code: {close_code}, chat_id: {self.chat_id}")
        try:
            # Leave the room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            
            # When customer disconnects, delete the chat completely
            if hasattr(self, 'is_agent') and not self.is_agent:
                logger.debug(f"Customer disconnect detected, deleting chat session: {self.chat_id}")
                session = await self.get_chat_session()
                if session:
                    # Completely delete all messages
                    await self.permanently_delete_all_messages(session)
                    
                    # Delete the chat session itself
                    await self.permanently_delete_chat_session()
                    logger.debug(f"Chat session and all messages completely deleted on disconnect: {self.chat_id}")
            else:
                logger.debug(f"Agent or unknown disconnected: {self.chat_id}, not deleting chat")
        except Exception as e:
            logger.error(f"Error in disconnect: {str(e)}")
            logger.error(traceback.format_exc())
    
    async def receive(self, text_data):
        """Process incoming messages from clients."""
        print(f"Received message: {text_data}")
        
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type', 'chat_message')
            
            # Handle different message types
            if message_type == 'close_chat':
                await self.process_close_chat(text_data_json)
            elif message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'content': 'Server received ping'
                }))
                print(f"Sent pong response to {self.chat_id}")
            elif message_type == 'chat_connect':
                # Send immediate confirmation for connect message
                await self.send(text_data=json.dumps({
                    'type': 'system',
                    'message': 'Connection established',
                    'timestamp': timezone.now().isoformat()
                }))
            elif message_type == 'user_waiting':
                # Better handling for user waiting notifications
                await self.handle_user_waiting(text_data_json)
            elif message_type == 'message':
                # Handle regular chat message
                message = text_data_json.get('message', '')
                username = text_data_json.get('username', 'Anonymous')
                is_agent = text_data_json.get('is_agent', False)
                client_message_id = text_data_json.get('client_message_id', None)
                
                # Log the message details for debugging
                print(f"Processing chat message: message='{message}', username='{username}', is_agent={is_agent}")
                
                # Save message to database if enabled
                message_data = await self.save_message(message, username, is_agent)
                
                # Mark if this is an agent
                if not hasattr(self, 'is_agent'):
                    self.is_agent = is_agent
                
                # Determine which message ID to use - prefer DB id, fallback to client ID
                message_id = None
                if message_data and 'id' in message_data:
                    message_id = message_data['id']
                elif client_message_id:
                    message_id = client_message_id
                
                # Broadcast message to the room group
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': message,
                        'username': username,
                        'is_agent': is_agent,
                        'timestamp': timezone.now().isoformat(),
                        'message_id': message_id
                    }
                )
                print(f"Chat message broadcast to group: {self.room_group_name}")
            else:
                # Legacy format handling
                await self.process_legacy_message(text_data_json)
        except json.JSONDecodeError:
            print(f"Error decoding JSON: {text_data}")
        except Exception as e:
            print(f"Error processing message: {e}")
            traceback.print_exc()
    
    async def chat_message(self, event):
        """Handler for chat messages"""
        try:
            # Format message with type 'message' to match client expectations
            message_payload = {
                'type': 'message',
                'message': event['message'],
                'username': event['username'],
                'is_agent': event['is_agent'],
                'timestamp': event['timestamp']
            }
            
            # Include message_id if available
            if 'message_id' in event and event['message_id']:
                message_payload['message_id'] = event['message_id']
            
            # Convert to JSON and send to client
            await self.send(text_data=json.dumps(message_payload))
            
            # Log successful message delivery
            print(f"Message sent to client ({self.channel_name}): {message_payload['message'][:30]}...")
            logger.debug(f"Chat message sent to client for chat: {self.chat_id}")
        except Exception as e:
            logger.error(f"Error sending chat message: {str(e)}")
            logger.error(traceback.format_exc())
    
    async def system_message(self, event):
        """Send system message to WebSocket"""
        logger.debug(f"System message sent for chat: {self.chat_id}")
        message = event.get('message', '')
        timestamp = event.get('timestamp', timezone.now().isoformat())
        
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'system',
            'message': message,
            'timestamp': timestamp
        }))
        
        logger.debug(f"System message sent to client for chat: {self.chat_id}")

    async def status_update(self, event):
        """Send status update to WebSocket"""
        logger.debug(f"Status update for chat: {self.chat_id}")
        status = event.get('status', '')
        timestamp = event.get('timestamp', timezone.now().isoformat())
        
        # Send status update to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'status': status,
            'timestamp': timestamp
        }))
        
        logger.debug(f"Status update sent to client for chat: {self.chat_id}, status: {status}")
    
    @database_sync_to_async
    def check_session_exists(self):
        """Check if the chat session exists and is active"""
        try:
            session = ChatSession.objects.get(id=self.chat_id)
            return session.is_active
        except ChatSession.DoesNotExist:
            logger.warning(f"Chat session does not exist: {self.chat_id}")
            return False
        except Exception as e:
            logger.error(f"Error checking if session exists: {str(e)}")
            return False
    
    @database_sync_to_async
    def save_message(self, message, username, is_agent):
        """Save a message to the database"""
        try:
            session = ChatSession.objects.get(id=self.chat_id)
            
            # Get sender (could be user or agent)
            sender = None
            if is_agent and session.agent:
                sender = session.agent
            elif not is_agent and session.user:
                sender = session.user
            
            message = ChatMessage.objects.create(
                chat_session=session,
                sender=sender,
                sender_name=username,
                is_agent=is_agent,
                content=message
            )
            
            return {
                'id': message.id,
                'content': message.content,
                'timestamp': message.timestamp
            }
        except ChatSession.DoesNotExist:
            logger.warning(f"Chat session not found when saving message: {self.chat_id}")
            return None
        except Exception as e:
            logger.error(f"Error saving message: {str(e)}")
            return None
    
    @database_sync_to_async
    def assign_agent(self, agent_username):
        """Assign an agent to this chat session"""
        try:
            session = ChatSession.objects.get(id=self.chat_id)
            agent = User.objects.get(username=agent_username)
            session.assign_to_agent(agent)
            
            # Create a system message about agent assignment
            ChatMessage.objects.create(
                chat_session=session,
                sender=None,
                sender_name="System",
                is_agent=True,
                content=f"{agent_username} has been assigned to this chat",
                message_type="system"
            )
            
            return True
        except (ChatSession.DoesNotExist, User.DoesNotExist) as e:
            logger.warning(f"Error assigning agent: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error assigning agent: {str(e)}")
            return False
    
    @database_sync_to_async
    def close_chat_session(self):
        """Close the chat session"""
        try:
            session = ChatSession.objects.get(id=self.chat_id)
            session.close()
            
            # Create a system message about session closure
            ChatMessage.objects.create(
                chat_session=session,
                sender=None,
                sender_name="System",
                is_agent=True,
                content="Chat session has been closed",
                message_type="system"
            )
            
            return True
        except ChatSession.DoesNotExist:
            logger.warning(f"Chat session not found when closing: {self.chat_id}")
            return False
        except Exception as e:
            logger.error(f"Error closing chat session: {str(e)}")
            return False

    @database_sync_to_async
    def get_chat_session(self):
        """Retrieve the chat session"""
        try:
            return ChatSession.objects.get(id=self.chat_id)
        except ChatSession.DoesNotExist:
            logger.warning(f"Chat session not found: {self.chat_id}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving chat session: {str(e)}")
            return None

    @database_sync_to_async
    def delete_all_messages(self, session):
        """Delete all messages for this chat session"""
        try:
            # Check if the session has messages
            if session.messages.exists():
                logger.info(f"Deleting all messages for chat session: {self.chat_id}")
                # Delete all messages for this session
                deleted_count = session.messages.all().delete()[0]
                logger.info(f"Successfully deleted {deleted_count} messages for chat session: {self.chat_id}")
                
                # Add a final system message recording the deletion
                ChatMessage.objects.create(
                    chat_session=session,
                    sender=None,
                    sender_name="System",
                    is_agent=True,
                    content="All previous messages have been deleted",
                    message_type="system"
                )
                return deleted_count
            else:
                logger.info(f"No messages to delete for chat session: {self.chat_id}")
                return 0
        except Exception as e:
            logger.error(f"Error deleting messages: {str(e)}")
            logger.error(traceback.format_exc())
            return 0

    def delete_all_messages_sync(self, session):
        """Synchronous version of delete_all_messages"""
        try:
            # Check if the session has messages
            if session.messages.exists():
                logger.info(f"Deleting all messages for chat session: {self.chat_id}")
                # Delete all messages for this session
                deleted_count = session.messages.all().delete()[0]
                logger.info(f"Successfully deleted {deleted_count} messages for chat session: {self.chat_id}")
                
                # Add a final system message recording the deletion
                ChatMessage.objects.create(
                    chat_session=session,
                    sender=None,
                    sender_name="System",
                    is_agent=True,
                    content="All previous messages have been deleted",
                    message_type="system"
                )
                return deleted_count
            else:
                logger.info(f"No messages to delete for chat session: {self.chat_id}")
                return 0
        except Exception as e:
            logger.error(f"Error deleting messages: {str(e)}")
            logger.error(traceback.format_exc())
            return 0

    def close_chat_session_sync(self):
        """Synchronous version of close_chat_session"""
        try:
            session = ChatSession.objects.get(id=self.chat_id)
            session.close()
            
            # Create a system message about session closure
            ChatMessage.objects.create(
                chat_session=session,
                sender=None,
                sender_name="System",
                is_agent=True,
                content="Chat session has been closed",
                message_type="system"
            )
            
            return True
        except ChatSession.DoesNotExist:
            logger.warning(f"Chat session not found when closing: {self.chat_id}")
            return False
        except Exception as e:
            logger.error(f"Error closing chat session: {str(e)}")
            return False

    def get_chat_session_sync(self):
        """Synchronous version of get_chat_session"""
        try:
            return ChatSession.objects.get(id=self.chat_id)
        except ChatSession.DoesNotExist:
            logger.warning(f"Chat session not found: {self.chat_id}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving chat session: {str(e)}")
            return None

    async def process_close_chat(self, data):
        """Process close chat messages asynchronously"""
        try:
            print(f"Processing close_chat request for session {self.chat_id}")
            chat_session = await self.get_chat_session()
            
            if not chat_session:
                print(f"Warning: Cannot find chat session {self.chat_id} for close_chat event")
                return
            
            # First notify all clients about the closure 
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'system_message',
                    'message': 'This chat has been closed.',
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            # Mark the chat as closed in the database
            result = await self.close_chat_session()
            print(f"Chat session closed result: {result}")
            
            # Send a close status message
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'status_update',
                    'status': 'closed',
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            print(f"Chat {self.chat_id} closed successfully")
        except Exception as e:
            print(f"Error handling close_chat: {str(e)}")
            traceback.print_exc()
        
    async def process_legacy_message(self, data):
        """Process messages in the legacy format"""
        message = data.get('message', '')
        username = data.get('username', 'Anonymous')
        is_agent = data.get('is_agent', False)
        
        print(f"Processing legacy message format: {message[:30]}...")
        
        # Save message to database
        message_data = await self.save_message(message, username, is_agent)
        
        # Broadcast message to the room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'username': username,
                'is_agent': is_agent,
                'timestamp': timezone.now().isoformat(),
                'message_id': message_data.get('id') if message_data else None
            }
        )

    async def handle_user_waiting(self, data):
        """Handle a user waiting for an agent"""
        print(f"User waiting notification for chat: {self.chat_id}")
        
        try:
            # Update the chat session in the database
            session = await self.get_chat_session()
            if session:
                await self.update_chat_status(session, 'waiting')
                
                # Create a system message for this notification
                await self.save_system_message("User is waiting for an agent")
                
                # Notify agents about this waiting chat - use channel layer to send to all agents
                channel_layer = get_channel_layer()
                
                # Broadcast to agent notification group
                await channel_layer.group_send(
                    'agent_notifications',
                    {
                        'type': 'user_waiting_notification',
                        'chat_id': str(self.chat_id),
                        'message': data.get('message', 'User waiting for an agent'),
                        'timestamp': data.get('timestamp', timezone.now().isoformat())
                    }
                )
                
                print(f"Sent agent notification for chat: {self.chat_id}")
                
                # Also send confirmation back to the user
                await self.send(text_data=json.dumps({
                    'type': 'system_message',
                    'message': 'We have notified our agents. Someone will be with you shortly.',
                    'timestamp': timezone.now().isoformat()
                }))
        except Exception as e:
            print(f"Error in handle_user_waiting: {e}")
            
    @database_sync_to_async
    def update_chat_status(self, session, status):
        """Update chat session status"""
        try:
            session.status = status
            session.save(update_fields=['status'])
            print(f"Updated chat session {session.id} status to: {status}")
            return True
        except Exception as e:
            print(f"Error updating chat status: {e}")
            return False
            
    @database_sync_to_async
    def save_system_message(self, message):
        """Save a system message to the chat"""
        try:
            session = ChatSession.objects.get(id=self.chat_id)
            ChatMessage.objects.create(
                chat_session=session,
                sender=None,
                sender_name="System",
                content=message,
                message_type="system",
                is_agent=True
            )
            return True
        except Exception as e:
            print(f"Error saving system message: {e}")
            return False

    def handle_chat_message(self, data):
        """Handle regular chat message"""
        message = data.get('message', '')
        username = data.get('username', 'Anonymous')
        is_agent = data.get('is_agent', False)
        
        # Set flag to track if this is an agent
        if not hasattr(self, 'is_agent'):
            self.is_agent = is_agent
        
        print(f"Processing chat message in handle_chat_message: message='{message}', username='{username}', is_agent={is_agent}")
        
        # Save message to database
        message_obj = self.save_message_sync(message, username, is_agent)
        if not message_obj:
            logger.error(f"Failed to save message for chat: {self.chat_id}")
            text_data = json.dumps({
                'type': 'error',
                'message': 'Failed to save message'
            })
            async_to_sync(self.send)(text_data)
            return
        
        # Send message to room group
        async_to_sync(self.channel_layer.group_send)(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'username': username,
                'is_agent': is_agent,
                'timestamp': message_obj['timestamp'].isoformat()
            }
        )
        
        # Also send immediate confirmation to the sender
        text_data = json.dumps({
            'type': 'message',
            'message': message,
            'username': username,
            'is_agent': is_agent,
            'timestamp': message_obj['timestamp'].isoformat(),
            'message_id': message_obj.get('id')
        })
        async_to_sync(self.send)(text_data)
        
        logger.debug(f"Message sent to group for chat: {self.chat_id}")
        print(f"Message broadcast to room group: {self.room_group_name}")

    def save_message_sync(self, message, username, is_agent):
        """Synchronous version of save_message"""
        try:
            session = ChatSession.objects.get(id=self.chat_id)
            
            # Get sender (could be user or agent)
            sender = None
            if is_agent and session.agent:
                sender = session.agent
            elif not is_agent and session.user:
                sender = session.user
            
            message = ChatMessage.objects.create(
                chat_session=session,
                sender=sender,
                sender_name=username,
                is_agent=is_agent,
                content=message
            )
            
            return {
                'id': message.id,
                'content': message.content,
                'timestamp': message.timestamp
            }
        except ChatSession.DoesNotExist:
            logger.warning(f"Chat session not found when saving message: {self.chat_id}")
            return None
        except Exception as e:
            logger.error(f"Error saving message: {str(e)}")
            return None

    def send_json(self, data):
        """Send JSON data to WebSocket"""
        text_data = json.dumps(data)
        async_to_sync(self.send)(text_data)

    @database_sync_to_async
    def permanently_delete_all_messages(self, session):
        """Completely delete all messages without recording deletion"""
        try:
            if session.messages.exists():
                # Delete all messages permanently
                deleted_count, _ = session.messages.all().delete()
                logger.info(f"Permanently deleted {deleted_count} messages for chat: {self.chat_id}")
                return deleted_count
            else:
                logger.info(f"No messages to delete for chat: {self.chat_id}")
                return 0
        except Exception as e:
            logger.error(f"Error permanently deleting messages: {str(e)}")
            logger.error(traceback.format_exc())
            return 0

    @database_sync_to_async
    def permanently_delete_chat_session(self):
        """Completely delete the chat session from database"""
        try:
            # Get the session
            session = ChatSession.objects.get(id=self.chat_id)
            
            # Delete the session completely
            session.delete()
            logger.info(f"Chat session completely deleted: {self.chat_id}")
            return True
        except ChatSession.DoesNotExist:
            logger.warning(f"Chat session not found for deletion: {self.chat_id}")
            return False
        except Exception as e:
            logger.error(f"Error permanently deleting chat session: {str(e)}")
            logger.error(traceback.format_exc())
            return False

class DebugConsumer(AsyncWebsocketConsumer):
    """Simple consumer for testing WebSocket connections"""
    async def connect(self):
        logger.debug("Debug WebSocket connection attempt")
        await self.accept()
        logger.debug("Debug WebSocket connection accepted")
        
        # Send a welcome message
        await self.send(text_data=json.dumps({
            'type': 'debug',
            'message': 'WebSocket connection successful!',
            'timestamp': timezone.now().isoformat()
        }))
    
    async def disconnect(self, close_code):
        logger.debug(f"Debug WebSocket disconnected with code: {close_code}")
    
    async def receive(self, text_data):
        logger.debug(f"Debug WebSocket received data: {text_data}")
        try:
            data = json.loads(text_data)
            # Echo back the received data
            await self.send(text_data=json.dumps({
                'type': 'debug_echo',
                'message': 'Echoing your message',
                'data': data,
                'timestamp': timezone.now().isoformat()
            }))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format',
                'timestamp': timezone.now().isoformat()
            }))
        except Exception as e:
            logger.error(f"Error in debug consumer: {str(e)}")
            logger.error(traceback.format_exc())
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Server error: {str(e)}',
                'timestamp': timezone.now().isoformat()
            }))

class AgentNotificationConsumer(AsyncWebsocketConsumer):
    """Consumer for agent notifications about new waiting chats"""
    
    async def connect(self):
        logger.debug("Agent notification WebSocket connection attempt")
        print("Agent notification WebSocket connection attempt")
        print(f"Channel name: {self.channel_name}")
        print(f"Connection scope: {self.scope}")
        
        # Join the agent_notifications group
        await self.channel_layer.group_add(
            'agent_notifications',
            self.channel_name
        )
        
        try:
            await self.accept()
            logger.debug("Agent notification WebSocket connection accepted")
            print("Agent notification WebSocket connection accepted")
            
            # Send a welcome message
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': 'Connected to agent notification system',
                'timestamp': timezone.now().isoformat()
            }))
        except Exception as e:
            logger.error(f"Error accepting WebSocket connection: {str(e)}")
            print(f"Error accepting WebSocket connection: {str(e)}")
            # Don't raise the exception - let the connection close gracefully
    
    async def disconnect(self, close_code):
        logger.debug(f"Agent notification WebSocket disconnected with code: {close_code}")
        print(f"Agent notification WebSocket disconnected with code: {close_code}")
        
        # Leave the group
        await self.channel_layer.group_discard(
            'agent_notifications',
            self.channel_name
        )
    
    async def user_waiting_notification(self, event):
        """
        Handle user_waiting_notification messages.
        This is called when a message is sent to the agent_notifications group
        with a type of user_waiting_notification.
        """
        logger.debug(f"Received user waiting notification: {event}")
        print(f"⚡ AGENT NOTIFICATION: Forwarding chat request {event.get('chat_id')} to connected agents")
        
        # Forward the notification to the WebSocket
        await self.send(text_data=json.dumps({
            'type': 'user_waiting',
            'chat_id': event.get('chat_id'),
            'message': event.get('message', 'User waiting for agent'),
            'timestamp': event.get('timestamp', timezone.now().isoformat())
        }))

class TestConsumer(AsyncWebsocketConsumer):
    """A simple test consumer for debugging WebSocket connections"""
    
    async def connect(self):
        print(f"TestConsumer: Connection attempt with scope: {self.scope}")
        await self.accept()
        print(f"TestConsumer: Connection accepted")
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'WebSocket connection established successfully',
            'timestamp': timezone.now().isoformat()
        }))
    
    async def disconnect(self, close_code):
        print(f"TestConsumer: Disconnected with code: {close_code}")
    
    async def receive(self, text_data):
        print(f"TestConsumer: Received message: {text_data}")
        
        try:
            data = json.loads(text_data)
            # Echo the message back with a timestamp
            await self.send(text_data=json.dumps({
                'type': 'echo',
                'received_data': data,
                'message': 'Message received and echoed back',
                'timestamp': timezone.now().isoformat()
            }))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format',
                'timestamp': timezone.now().isoformat()
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Error processing message: {str(e)}',
                'timestamp': timezone.now().isoformat()
            })) 