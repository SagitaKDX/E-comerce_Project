from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.db.models import Q, Count, Avg, F, ExpressionWrapper, fields, DurationField
from django.utils import timezone
from django.db.models.functions import TruncDate
import datetime
import csv
from .models import ChatSession, ChatMessage
import json
import uuid
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.urls import reverse
import logging
import traceback
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.conf import settings
from django.template.loader import render_to_string
import django

logger = logging.getLogger('django.channels')

def start_chat(request):
    """Start a new chat session for a user"""
    if request.method == 'POST':
        subject = request.POST.get('subject', 'Support Chat')
        user_email = None # Initialize

        # Determine if it's an AJAX request early
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if request.user.is_authenticated:
            existing_chat = ChatSession.objects.filter(
                user=request.user,
                is_active=True
            ).first()

            if existing_chat:
                chat_session = existing_chat # Use existing active chat
            else:
                # Create a new chat session for authenticated user
                chat_session = ChatSession.objects.create(
                    user=request.user,
                    subject=subject
                )
        else: # Anonymous user
            user_email = request.POST.get('email', '')
            if not user_email:
                # If it's an AJAX request, return JSON error
                if is_ajax:
                    return JsonResponse({'success': False, 'error': 'Email is required for anonymous chat.'}, status=400)
                else: # If not AJAX, render an error page (or redirect)
                    response = render(request, 'livechat/error.html', {'error': 'Email is required for anonymous chat'})
                    if 'X-Frame-Options' in response: del response['X-Frame-Options']
                    return response # Return HTML page for non-AJAX

            session_key = request.session.session_key
            if not session_key:
                request.session.save()
                session_key = request.session.session_key

            # Find existing active anonymous chat for this session/email or create new
            existing_chat = ChatSession.objects.filter(
                session_key=session_key,
                user_email=user_email,
                is_active=True,
                user__isnull=True # Ensure it's an anonymous session
            ).first()

            if existing_chat:
                 chat_session = existing_chat
            else:
                # Create a new chat session for anonymous user
                chat_session = ChatSession.objects.create(
                    subject=subject,
                    user_email=user_email,
                    session_key=session_key
                )

        # Create initial system message only if it's a truly new chat session (or wasn't created before)
        if not ChatMessage.objects.filter(chat_session=chat_session, message_type="system", content__startswith="Chat session started").exists():
            ChatMessage.objects.create(
                chat_session=chat_session,
                sender=None, # System messages have no user sender
                sender_name="System",
                content="Chat session started. Please wait for a support agent.",
                message_type="system",
                is_agent=True # Often treated like agent messages for display/notification purposes
            )

        # Check if it's an AJAX request *again* before returning
        if is_ajax:
            return JsonResponse({
                'success': True,
                'chat_id': str(chat_session.id) # Return chat_id as string
            })
        else:
            # Normal form submission (non-AJAX POST) - redirect to the chat room
            # Use the correct view name for the embedded chat
            return redirect('livechat:embedded_chat_room', chat_id=chat_session.id)

    # GET request - show the start chat form (assuming you have one)
    # Or potentially redirect to home or show an error if direct GET access isn't intended
    response = render(request, 'livechat/start_chat.html') # Adjust template if needed
    # Ensure it can be embedded if needed
    if 'X-Frame-Options' in response: del response['X-Frame-Options']
    return response

def chat_room(request, chat_id):
    """Render the chat room template"""
    try:
        chat_session = ChatSession.objects.get(id=chat_id)
        messages = ChatMessage.objects.filter(chat_session=chat_session).order_by('timestamp')
        
        # Check if user is agent
        is_agent = request.user.is_staff or request.user.is_superuser
        
        # Get recent orders if user is authenticated (for agent view)
        recent_orders = []
        if is_agent and chat_session.user:
            try:
                from store.models import Order
                recent_orders = Order.objects.filter(user=chat_session.user).order_by('-created_at')[:3]
            except ImportError:
                pass
        
        # Get username for display
        if request.user.is_authenticated:
            username = request.user.get_full_name() or request.user.username
        else:
            username = "Guest"
            
        # Check if this is an embedded view
        is_embedded = request.GET.get('embedded', False)
        
        # Add the page viewed message if not an agent
        if not is_agent and not chat_session.page_viewed:
            system_message = ChatMessage(
                chat_session=chat_session,
                sender=None,
                message_type='system',
                content="User viewed the chat page."
            )
            system_message.save()
            chat_session.page_viewed = True
            chat_session.save()
        
        context = {
            'chat_session': chat_session,
            'messages': messages,
            'chat_id': chat_id,
            'is_agent': is_agent,
            'username': username,
            'is_embedded': is_embedded,
            'recent_orders': recent_orders,
        }
        
        # Use different template for agents
        if is_agent:
            return render(request, 'livechat/agent_chat_room.html', context)
        else:
            return render(request, 'livechat/chat_room.html', context)
    except ChatSession.DoesNotExist:
        return render(request, 'livechat/error.html', {'error': 'Chat session not found'})

def embedded_chat_room(request, chat_id):
    """Special view for embedded chat that removes X-Frame-Options"""
    try:
        chat_session = ChatSession.objects.get(id=chat_id)
        messages = ChatMessage.objects.filter(chat_session=chat_session).order_by('timestamp')
        
        # Check if user is agent
        is_agent = request.user.is_staff or request.user.is_superuser
        
        context = {
            'chat_session': chat_session,
            'messages': messages,
            'chat_id': chat_id,
            'is_agent': is_agent,
            'username': request.user.get_username() if request.user.is_authenticated else 'Guest',
            'embedded': True,
            'debug': settings.DEBUG,
        }
        
        response = render(request, 'livechat/chat_room.html', context)
        response['X-Frame-Options'] = 'ALLOWALL'
        return response
    except ChatSession.DoesNotExist:
        response = render(request, 'livechat/error.html', {'error': 'Chat session not found'})
        if 'X-Frame-Options' in response:
            del response['X-Frame-Options']
        return response

@login_required
def agent_dashboard(request):
    """Dashboard for support agents to see all active chats"""
    # Check if user is allowed to access this page
    if not (hasattr(request.user, 'profile') and request.user.profile.is_crm_user) and not request.user.is_staff:
        return redirect('home')
    
    # Get all active chat sessions
    waiting_chats = ChatSession.objects.filter(status='waiting', is_active=True)
    assigned_chats = ChatSession.objects.filter(
        Q(status='active', is_active=True) & 
        (Q(agent=request.user) | Q(agent__isnull=True))
    )
    
    context = {
        'waiting_chats': waiting_chats,
        'assigned_chats': assigned_chats
    }
    
    return render(request, 'livechat/agent_dashboard.html', context)

@login_required
@csrf_exempt
def assign_chat(request):
    """API to assign a chat to an agent"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            chat_id = data.get('chat_id')
            
            # Check if user is allowed to be an agent
            if not (hasattr(request.user, 'profile') and request.user.profile.is_crm_user) and not request.user.is_staff:
                return JsonResponse({'error': 'Not authorized'}, status=403)
            
            # Get chat session
            chat_session = ChatSession.objects.get(id=chat_id)
            
            # Assign agent
            chat_session.assign_to_agent(request.user)
            
            return JsonResponse({'success': True})
        
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@require_POST
@csrf_exempt
def close_chat(request):
    """API endpoint to close a chat session"""
    data = json.loads(request.body)
    chat_id = data.get('chat_id')
    
    if not chat_id:
        return JsonResponse({'success': False, 'error': 'Chat ID required'}, status=400)
    
    try:
        chat_session = ChatSession.objects.get(id=chat_id)
        
        # Check permissions 
        is_agent = request.user.is_authenticated and hasattr(request.user, 'agent_profile')
        is_participant = (chat_session.user == request.user) if request.user.is_authenticated else False
        is_anonymous_with_session = False
        
        # Check if anonymous user with matching session key
        if not request.user.is_authenticated and chat_session.session_key:
            is_anonymous_with_session = (request.session.session_key == chat_session.session_key)
        
        # Allow closing if user is agent, participant, or anonymous with matching session
        if not (is_agent or is_participant or is_anonymous_with_session):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        # Close the chat session
        chat_session.close(auto_delete=True)
        
        # Log the closing
        logger.info(f"Chat {chat_id} closed by {'agent' if is_agent else 'user'}")
        
        # Send notification to channel layer if available
        # This is for real-time notification via WebSockets
        try:
            channel_layer = get_channel_layer()
            room_name = f'chat_{chat_id}'
            
            async_to_sync(channel_layer.group_send)(
                room_name,
                {
                    'type': 'system_message',
                    'message': 'Chat has been closed by the server.',
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            # Also send status update
            async_to_sync(channel_layer.group_send)(
                room_name,
                {
                    'type': 'status_update',
                    'status': 'closed',
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            logger.info(f"Sent WebSocket closure notifications for chat {chat_id}")
        except Exception as e:
            logger.warning(f"Could not send WebSocket notification for chat closure: {str(e)}")
        
        return JsonResponse({'success': True})
    except ChatSession.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Chat not found'}, status=404)
    except Exception as e:
        logger.exception(f"Error closing chat {chat_id}: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def chat_analytics(request):
    """Analytics dashboard for chat performance"""
    # Check if user is allowed to access this page
    if not (hasattr(request.user, 'profile') and request.user.profile.is_crm_user) and not request.user.is_staff:
        return redirect('home')
    
    # Date filtering
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - datetime.timedelta(days=days)
    
    # Basic stats
    total_chats = ChatSession.objects.filter(started_at__gte=start_date).count()
    closed_chats = ChatSession.objects.filter(started_at__gte=start_date, status='closed').count()
    avg_duration = ChatSession.objects.filter(
        started_at__gte=start_date,
        status='closed',
        ended_at__isnull=False
    ).annotate(
        duration_seconds=ExpressionWrapper(
            F('ended_at') - F('started_at'),
            output_field=DurationField()
        )
    ).aggregate(avg_duration=Avg('duration_seconds'))
    
    # Chats per day
    chats_per_day = ChatSession.objects.filter(
        started_at__gte=start_date
    ).annotate(
        date=TruncDate('started_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    # Chats by subject
    chats_by_subject = ChatSession.objects.filter(
        started_at__gte=start_date
    ).values('subject').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Agent performance
    agent_performance = ChatSession.objects.filter(
        started_at__gte=start_date,
        agent__isnull=False,
        status='closed'
    ).values(
        'agent__username',
        'agent__first_name',
        'agent__last_name'
    ).annotate(
        count=Count('id'),
        avg_duration=Avg(ExpressionWrapper(
            F('ended_at') - F('started_at'),
            output_field=DurationField()
        ))
    ).order_by('-count')
    
    context = {
        'total_chats': total_chats,
        'closed_chats': closed_chats,
        'avg_duration': avg_duration.get('avg_duration') if avg_duration.get('avg_duration') else datetime.timedelta(0),
        'completion_rate': round((closed_chats / total_chats * 100) if total_chats > 0 else 0, 1),
        'chats_per_day': list(chats_per_day),
        'chats_by_subject': list(chats_by_subject),
        'agent_performance': list(agent_performance),
        'selected_days': days
    }
    
    return render(request, 'livechat/chat_analytics.html', context)

@login_required
def export_chat_transcript(request, chat_id):
    """Export chat transcript to CSV"""
    # Check if user is allowed to access this page
    if not (hasattr(request.user, 'profile') and request.user.profile.is_crm_user) and not request.user.is_staff:
        return redirect('home')
    
    try:
        chat_session = ChatSession.objects.get(id=chat_id)
        messages = chat_session.messages.all().order_by('timestamp')
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="chat_transcript_{chat_id}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Timestamp', 'Sender', 'Message', 'Type'])
        
        for message in messages:
            writer.writerow([
                message.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                message.sender_name,
                message.content,
                message.get_message_type_display()
            ])
        
        return response
    except ChatSession.DoesNotExist:
        return render(request, 'livechat/error.html', {'error': 'Chat session not found'})

@login_required
def quick_responses(request):
    """View for managing quick response templates"""
    if not (hasattr(request.user, 'profile') and request.user.profile.is_crm_user) and not request.user.is_staff:
        return redirect('home')
    
    # This is a placeholder for future implementation
    # Would need to create a QuickResponse model
    
    context = {
        'response_categories': [
            {'name': 'Greetings', 'responses': [
                {'text': 'Hello! How can I help you today?'},
                {'text': 'Welcome to our support chat. What brings you here today?'},
                {'text': 'Thank you for contacting us. How may I assist you?'}
            ]},
            {'name': 'Order Issues', 'responses': [
                {'text': 'I understand you\'re having an issue with your order. Could you please provide your order number?'},
                {'text': 'I\'ll be happy to help you with your order concern. Let me look that up for you.'},
                {'text': 'I apologize for the inconvenience with your order. Let\'s get this resolved for you.'}
            ]},
            {'name': 'Technical Support', 'responses': [
                {'text': 'Could you please describe what technical issue you\'re experiencing?'},
                {'text': 'Have you tried clearing your browser cache and cookies?'},
                {'text': 'Would it be possible for you to share a screenshot of the error you\'re seeing?'}
            ]},
            {'name': 'Closing', 'responses': [
                {'text': 'Is there anything else I can help you with today?'},
                {'text': 'Thank you for chatting with us. If you have any other questions, feel free to contact us again.'},
                {'text': 'I\'m glad we could resolve your issue. Have a great day!'}
            ]}
        ]
    }
    
    return render(request, 'livechat/quick_responses.html', context)

# @login_required
# def chat_history(request):
#     """View chat history for CRM users"""
#     # Check if user is allowed to access this page
#     if not (hasattr(request.user, 'profile') and request.user.profile.is_crm_user) and not request.user.is_staff:
#         return redirect('home')
#     
#     # Handle filters
#     status = request.GET.get('status', 'all')
#     agent_id = request.GET.get('agent', 'all')
#     search_query = request.GET.get('q', '')
#     
#     # Base queryset
#     queryset = ChatSession.objects.all()
#     
#     # Apply filters
#     if status != 'all':
#         queryset = queryset.filter(status=status)
#     
#     if agent_id != 'all' and agent_id.isdigit():
#         queryset = queryset.filter(agent_id=agent_id)
#     
#     if search_query:
#         # Search by email, subject, or chat ID
#         queryset = queryset.filter(
#             Q(user_email__icontains=search_query) |
#             Q(subject__icontains=search_query) |
#             Q(id__icontains=search_query)
#         )
#     
#     # Get all agents for the filter dropdown
#     agents = User.objects.filter(
#         Q(profile__is_crm_user=True) | Q(is_staff=True)
#     ).values('id', 'username', 'first_name', 'last_name')
#     
#     # Pagination
#     page = request.GET.get('page', 1)
#     paginator = Paginator(queryset.order_by('-started_at'), 20)
#     
#     try:
#         chats = paginator.page(page)
#     except PageNotAnInteger:
#         chats = paginator.page(1)
#     except EmptyPage:
#         chats = paginator.page(paginator.num_pages)
#     
#     context = {
#         'chats': chats,
#         'agents': agents,
#         'selected_status': status,
#         'selected_agent': agent_id,
#         'search_query': search_query,
#         'status_choices': ChatSession.STATUS_CHOICES,
#     }
#     
#     return render(request, 'livechat/chat_history.html', context)

# @login_required
# def chat_detail(request, chat_id):
#     """View detailed information about a chat session"""
#     # Check if user is allowed to access this page
#     if not (hasattr(request.user, 'profile') and request.user.profile.is_crm_user) and not request.user.is_staff:
#         return redirect('home')
#     
#     try:
#         chat_session = ChatSession.objects.get(id=chat_id)
#         messages = chat_session.messages.all().order_by('timestamp')
#         
#         # Get username if available
#         username = None
#         if chat_session.user:
#             username = chat_session.user.get_full_name() or chat_session.user.username
#         elif chat_session.user_email:
#             username = chat_session.user_email
#         
#         context = {
#             'chat': chat_session,
#             'messages': messages,
#             'username': username,
#         }
#         
#         return render(request, 'livechat/chat_detail.html', context)
#     
#     except ChatSession.DoesNotExist:
#         return render(request, 'livechat/error.html', {'error': 'Chat session not found'})

def floating_chat(request):
    """Render the floating chat widget for inclusion in the base template"""
    # Check if user already has an active chat
    chat_id = None
    chat_session = None
    
    if request.user.is_authenticated:
        chat_session = ChatSession.objects.filter(
            user=request.user,
            is_active=True
        ).first()
        
        if chat_session:
            chat_id = chat_session.id
            username = request.user.get_full_name() or request.user.username
            is_agent = request.user.profile.is_crm_user if hasattr(request.user, 'profile') else False
        else:
            username = request.user.get_full_name() or request.user.username
            is_agent = False
    else:
        username = "Guest"
        is_agent = False
    
    context = {
        'chat_id': chat_id,
        'chat_session': chat_session,
        'username': username,
        'is_agent': is_agent,
    }
    
    return render(request, 'livechat/floating_chat.html', context)

def embedded_chat(request, chat_id=None):
    """Render a chat session in an embedded view without header/footer"""
    if chat_id:
        # Existing chat - redirect to embedded chat room without frame options
        return redirect('livechat:embedded_chat_room', chat_id=chat_id)
    else:
        # New chat - show start form
        response = render(request, 'livechat/start_chat.html', {'embedded': True})
        # Remove X-Frame-Options header to allow embedding
        if 'X-Frame-Options' in response:
            del response['X-Frame-Options']
        return response

def test_chat_page(request):
    """Render a test page for debugging the chat widget"""
    context = {
        'now': timezone.now(),
    }
    response = render(request, 'livechat/test_chat.html', context)
    
    # Remove X-Frame-Options header to allow embedding
    if 'X-Frame-Options' in response:
        del response['X-Frame-Options']
    
    return response

@csrf_exempt
def websocket_health_check(request):
    """
    Diagnostic endpoint to check if WebSocket server is running properly
    """
    try:
        channel_layer = get_channel_layer()
        timestamp = timezone.now().isoformat()
        
        # Try to create a test group
        test_group = f"health_check_{timestamp}"
        
        # Test async functionality
        async_to_sync(channel_layer.group_add)(test_group, test_group)
        async_to_sync(channel_layer.group_discard)(test_group, test_group)
        
        return JsonResponse({
            'status': 'ok',
            'timestamp': timestamp,
            'channel_layer_type': channel_layer.__class__.__name__,
            'message': 'WebSocket server is running correctly'
        })
    except Exception as e:
        logger.error(f"WebSocket health check failed: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'status': 'error',
            'timestamp': timezone.now().isoformat(),
            'error': str(e),
            'message': 'WebSocket server configuration issue detected'
        }, status=500)

def websocket_test(request):
    """Simple test page for WebSocket connections"""
    response = render(request, 'livechat/websocket_test.html')
    
    # Remove X-Frame-Options header to allow embedding
    if 'X-Frame-Options' in response:
        del response['X-Frame-Options']
    
    return response

def simple_test_view(request):
    return HttpResponse("Hello from simple_test_view!")

def websocket_debug(request):
    """View for testing WebSocket connections"""
    return render(request, 'websocket_debug.html')

def debug_chat_test(request):
    """Debug page for testing chat functionality with detailed logs"""
    context = {
        'timestamp': timezone.now().isoformat(),
        'server_version': 'Django ' + django.__version__,
        'csrf_token': request.META.get("CSRF_COOKIE", ""),
        'user': {
            'is_authenticated': request.user.is_authenticated,
            'username': request.user.username if request.user.is_authenticated else 'Anonymous',
        },
        'client_ip': request.META.get('REMOTE_ADDR', '0.0.0.0'),
        'debug_mode': settings.DEBUG,
    }
    
    response = render(request, 'livechat/debug_chat_test.html', context)
    # Remove X-Frame-Options header to allow embedding for testing
    if 'X-Frame-Options' in response:
        del response['X-Frame-Options']
    return response

@csrf_exempt
def create_chat_room(request):
    """API endpoint to create a new chat room and return its ID"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    try:
        logger.info(f"[DEBUG] Create chat room API called. User authenticated: {request.user.is_authenticated}")
        
        # Create a new chat session
        if request.user.is_authenticated:
            # Check if user already has an active chat
            existing_chat = ChatSession.objects.filter(
                user=request.user,
                is_active=True
            ).first()
            
            if existing_chat:
                # Return existing chat
                logger.info(f"[DEBUG] Returning existing chat session: {existing_chat.id}")
                return JsonResponse({
                    'success': True,
                    'room_id': str(existing_chat.id),
                    'is_new': False
                })
            
            # Create a new chat session
            chat_session = ChatSession.objects.create(
                user=request.user,
                subject="Support Chat",
                status='waiting'  # Explicitly set status to waiting
            )
            logger.info(f"[DEBUG] Created new chat session for authenticated user: {chat_session.id}")
        else:
            # For anonymous users, create a session with session key
            session_key = request.session.session_key
            if not session_key:
                request.session.save()
                session_key = request.session.session_key
            
            # Get user's email or IP for identification
            user_email = request.POST.get('email', 'guest@example.com')
            # Get user's IP address for tracking
            user_ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
            
            logger.info(f"[DEBUG] Creating chat for anonymous user. Session: {session_key}, IP: {user_ip}")
            
            # Create chat session for anonymous user
            chat_session = ChatSession.objects.create(
                subject="Support Chat",
                user_email=user_email,
                session_key=session_key,
                status='waiting'  # Explicitly set status to waiting
            )
            logger.info(f"[DEBUG] Created new chat session for anonymous user: {chat_session.id}")
        
        # Create initial system message
        ChatMessage.objects.create(
            chat_session=chat_session,
            sender=None,
            sender_name="System",
            content="Chat session started. Please wait for a support agent.",
            message_type="system",
            is_agent=True
        )
        
        # Try to notify agents via WebSocket channel if possible
        try:
            channel_layer = get_channel_layer()
            logger.info(f"[DEBUG] Attempting to notify agents about new chat: {chat_session.id}")
            # Broadcast to agent notification group
            async_to_sync(channel_layer.group_send)(
                'agent_notifications',
                {
                    'type': 'user_waiting_notification',
                    'chat_id': str(chat_session.id),
                    'timestamp': timezone.now().isoformat(),
                    'user_info': request.user.username if request.user.is_authenticated else 'Guest'
                }
            )
            logger.info(f"[DEBUG] Successfully sent agent notification for chat: {chat_session.id}")
        except Exception as e:
            logger.error(f"[DEBUG] Failed to send agent notification: {str(e)}")
        
        # Return success response with the chat room ID
        return JsonResponse({
            'success': True,
            'room_id': str(chat_session.id),
            'is_new': True
        })
    
    except Exception as e:
        logger.error(f"[DEBUG] Error creating chat room: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)

@csrf_exempt
def get_chat_info(request, chat_id):
    """API endpoint to get information about a chat"""
    try:
        chat_session = get_object_or_404(ChatSession, id=chat_id)
        
        # Get user information
        user_name = None
        user_email = chat_session.user_email
        
        if chat_session.user:
            user_name = chat_session.user.get_full_name() or chat_session.user.username
            if not user_email and chat_session.user.email:
                user_email = chat_session.user.email
        
        # Build response data
        data = {
            'id': str(chat_session.id),
            'subject': chat_session.subject,
            'status': chat_session.status,
            'is_active': chat_session.is_active,
            'started_at': chat_session.started_at.isoformat() if chat_session.started_at else None,
            'user_name': user_name,
            'user_email': user_email,
            'message_count': chat_session.messages.count(),
            'agent_assigned': chat_session.agent.username if chat_session.agent else None
        }
        
        return JsonResponse(data)
    except Exception as e:
        logger.error(f"Error getting chat info: {str(e)}")
        return JsonResponse({
            'error': str(e)
        }, status=500)

@login_required
def get_waiting_chats(request):
    """API endpoint to get the count of waiting chats"""
    try:
        # Check if user is allowed to access this data
        if not (hasattr(request.user, 'profile') and request.user.profile.is_crm_user) and not request.user.is_staff:
            return JsonResponse({'error': 'Not authorized'}, status=403)
        
        # Get count of waiting chats
        waiting_count = ChatSession.objects.filter(status='waiting', is_active=True).count()
        
        # Return basic information
        return JsonResponse({
            'success': True,
            'waiting_count': waiting_count,
            'timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting waiting chats: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
def create_session(request):
    """API endpoint to create a new chat session from the floating chat widget"""
    if request.method == 'POST':
        try:
            # Parse JSON data
            data = json.loads(request.body)
            subject = data.get('subject', 'General Inquiry')
            email = data.get('email')
            client_session_id = data.get('session_id')
            
            # Log incoming request
            logger.debug(f"Create session request: subject={subject}, email={email}, client_id={client_session_id}")
            
            # Get or create a chat session
            if request.user.is_authenticated:
                # For authenticated users, check for existing active sessions
                chat_session = ChatSession.objects.filter(
                    user=request.user,
                    is_active=True
                ).first()
                
                if not chat_session:
                    # Create new session
                    chat_session = ChatSession.objects.create(
                        id=uuid.UUID(client_session_id) if client_session_id else uuid.uuid4(),
                        user=request.user,
                        subject=subject,
                        user_email=request.user.email
                    )
            else:
                # For anonymous users
                session_key = request.session.session_key
                if not session_key:
                    request.session.save()
                    session_key = request.session.session_key
                
                # Try to use client's session ID if valid
                session_id = None
                if client_session_id:
                    try:
                        session_id = uuid.UUID(client_session_id)
                    except (ValueError, TypeError):
                        session_id = uuid.uuid4()
                else:
                    session_id = uuid.uuid4()
                
                # Create new chat session for anonymous user
                chat_session = ChatSession.objects.create(
                    id=session_id,
                    subject=subject,
                    user_email=email,
                    session_key=session_key
                )
            
            # Create initial system message
            ChatMessage.objects.create(
                chat_session=chat_session,
                sender=None,
                sender_name="System",
                content=f"Chat session started. Topic: {subject}",
                message_type="system",
                is_agent=True
            )
            
            # Notify agent dashboard of new chat
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                'agent_notifications',
                {
                    'type': 'user_waiting_notification',
                    'chat_id': str(chat_session.id),
                    'subject': subject,
                    'email': email or 'Anonymous',
                    'started_at': chat_session.started_at.isoformat()
                }
            )
            
            return JsonResponse({
                'success': True,
                'session_id': str(chat_session.id),
                'message': 'Chat session created successfully'
            })
            
        except Exception as e:
            logger.error(f"Error creating chat session: {str(e)}")
            logger.error(traceback.format_exc())
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    }, status=405)
