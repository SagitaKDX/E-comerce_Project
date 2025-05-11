from django.urls import path
from custom_admin.views import crm

app_name = 'crm'

urlpatterns = [
    path('', crm.crm_dashboard, name='crm_dashboard'),
    path('comments/', crm.comment_list, name='crm_comment_list'),
    path('comments/<int:pk>/', crm.comment_detail, name='crm_comment_detail'),
    path('analytics/', crm.crm_analytics, name='crm_analytics'),
    path('settings/', crm.crm_settings, name='crm_settings'),
    path('login/', crm.crm_login, name='crm_login'),
    path('users/<int:pk>/', crm.crm_user_detail, name='crm_user_detail'),
    path('users/', crm.crm_user_list, name='crm_user_list'),
    path('users/add/', crm.crm_user_add, name='crm_user_add'),
    path('orders/', crm.crm_order_list, name='crm_order_list'),
    path('orders/<int:pk>/', crm.crm_order_detail, name='crm_order_detail'),
    path('packages/', crm.crm_package_list, name='crm_package_list'),
    path('packages/<int:pk>/', crm.crm_package_detail, name='crm_package_detail'),
    path('products/', crm.crm_product_list, name='crm_product_list'),
    path('products/<int:pk>/', crm.crm_product_detail, name='crm_product_detail'),
    path('ratings/product/<int:rating_id>/mark-reviewed/', crm.mark_product_rating_reviewed, name='mark_product_rating_reviewed'),
    path('ratings/package/<int:rating_id>/mark-reviewed/', crm.mark_package_rating_reviewed, name='mark_package_rating_reviewed'),
] 