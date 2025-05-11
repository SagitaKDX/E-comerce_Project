from django.urls import path
from custom_admin.views import crm

app_name = 'crm'

urlpatterns = [
    path('dashboard/', crm.crm_dashboard, name='crm_dashboard'),
    path('comments/', crm.comment_list, name='crm_comment_list'),
    path('comments/<int:pk>/', crm.comment_detail, name='crm_comment_detail'),
    path('analytics/', crm.crm_analytics, name='crm_analytics'),
    path('settings/', crm.crm_settings, name='crm_settings'),
    path('login/', crm.crm_login, name='crm_login'),
    path('users/<int:pk>/', crm.crm_user_detail, name='crm_user_detail'),
    path('users/', crm.crm_user_list, name='crm_user_list'),
    path('orders/', crm.crm_order_list, name='crm_order_list'),
    path('orders/<int:pk>/', crm.crm_order_detail, name='crm_order_detail'),
] 