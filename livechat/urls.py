from django.urls import path
from django.shortcuts import render
from . import views

app_name = 'livechat'

urlpatterns = [
    path('start/', views.start_chat, name='start_chat'),
    path('chat/<str:chat_id>/', views.chat_room, name='chat_room'),
    path('embed-chat/<str:chat_id>/', views.embedded_chat_room, name='embedded_chat_room'),
    path('agent/dashboard/', views.agent_dashboard, name='agent_dashboard'),
    path('agent/analytics/', views.chat_analytics, name='chat_analytics'),
    path('agent/quick-responses/', views.quick_responses, name='quick_responses'),
    # path('agent/history/', views.chat_history, name='chat_history'),
    # path('agent/history/<str:chat_id>/', views.chat_detail, name='chat_detail'),
    path('api/assign-chat/', views.assign_chat, name='assign_chat'),
    path('api/close-chat/', views.close_chat, name='close_chat'),
    path('api/create-chat-room/', views.create_chat_room, name='create_chat_room'),
    path('api/create_session/', views.create_session, name='create_session'),
    path('api/chat-info/<str:chat_id>/', views.get_chat_info, name='get_chat_info'),
    path('api/waiting-chats/', views.get_waiting_chats, name='get_waiting_chats'),
    path('export/<str:chat_id>/', views.export_chat_transcript, name='export_transcript'),
    path('widget/', views.floating_chat, name='floating_chat'),
    path('embed/', views.embedded_chat, name='embedded_chat'),
    path('embed/<str:chat_id>/', views.embedded_chat, name='embedded_chat_with_id'),
    path('test/', views.test_chat_page, name='test_chat_page'),
    path('debug-test/', views.debug_chat_test, name='debug_chat_test'),
    path('websocket-health/', views.websocket_health_check, name='websocket_health_check'),
    path('websocket-test/', views.websocket_test, name='websocket_test'),
    path('simple-test/', views.simple_test_view, name='simple_test'),
    path('websocket-debug/', views.websocket_debug, name='websocket_debug'),
    path('ws-test/', lambda request: render(request, 'websocket_debug.html'), name='ws_test'),
] 