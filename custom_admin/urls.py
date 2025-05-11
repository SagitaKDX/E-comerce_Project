from django.urls import path
from custom_admin.views import dashboard
from custom_admin.views import category
from custom_admin.views import product
from custom_admin.views import user
from custom_admin.views import order
from custom_admin.views import banners
from custom_admin.views import analytics
from custom_admin.views import voucher
from custom_admin.views import package
from custom_admin.views import crm
from custom_admin.views import faq
from custom_admin.views.loyalty import (
    loyalty_dashboard, loyalty_tiers_list, loyalty_tier_create, loyalty_tier_edit, 
    loyalty_tier_delete, loyalty_customers_list, customer_loyalty_detail, 
    create_manual_voucher, loyalty_vouchers_list, loyalty_settings, recalculate_loyalty_tiers_view
)

app_name = 'admin_dashboard'

urlpatterns = [
    # Authentication
    path('login/', dashboard.admin_login, name='admin_login'),
    path('logout/', dashboard.admin_logout, name='admin_logout'),
    
    # Dashboard
    path('', dashboard.dashboard, name='dashboard'),
    
    # Analytics
    path('analytics/', analytics.overview, name='admin_analytics'),
    path('analytics/sales/', analytics.sales_chart, name='admin_sales_chart'),
    path('analytics/products/', analytics.product_analytics, name='admin_product_analytics'),
    path('analytics/customers/', analytics.customer_analytics, name='admin_customer_analytics'),
    path('api/chart-data/', analytics.chart_data_api, name='admin_chart_data'),
    
    # Categories
    path('categories/', category.category_list, name='admin_categories'),
    path('categories/add/', category.category_add, name='admin_category_add'),
    path('categories/edit/<int:pk>/', category.category_edit, name='admin_category_edit'),
    path('categories/delete/<int:pk>/', category.category_delete, name='admin_category_delete'),
    
    # Products
    path('products/', product.product_list, name='admin_products'),
    path('products/add/', product.product_add, name='admin_product_add'),
    path('products/edit/<int:pk>/', product.product_edit, name='admin_product_edit'),
    path('products/delete/<int:pk>/', product.product_delete, name='admin_product_delete'),
    
    # Packages
    path('packages/', package.package_list, name='admin_packages'),
    path('packages/add/', package.package_add, name='admin_package_add'),
    path('packages/edit/<int:pk>/', package.package_edit, name='admin_package_edit'),
    path('packages/delete/<int:pk>/', package.package_delete, name='admin_package_delete'),
    
    # Users
    path('users/', user.user_list, name='admin_users'),
    path('users/add/', user.user_add, name='admin_user_add'),
    path('users/edit/<int:pk>/', user.user_edit, name='admin_user_edit'),
    path('users/delete/<int:pk>/', user.user_delete, name='admin_user_delete'),
    path('users/reset-password/<int:pk>/', user.user_password_reset, name='admin_user_password_reset'),
    path('users/<int:pk>/', user.user_detail, name='admin_user_detail'),
    
    # Orders
    path('orders/', order.order_list, name='admin_orders'),
    path('orders/<int:pk>/', order.order_detail, name='admin_order_detail'),
    path('orders/<int:pk>/update-status/', order.order_update, name='admin_order_update'),
    
    # Promo Banners
    path('banners/', banners.banner_list, name='admin_banners'),
    path('banners/add/', banners.banner_add, name='admin_banner_add'),
    path('banners/edit/<int:pk>/', banners.banner_edit, name='admin_banner_edit'),
    path('banners/delete/<int:pk>/', banners.banner_delete, name='admin_banner_delete'),
    path('banners/reorder/', banners.banner_reorder, name='admin_banner_reorder'),
    
    # Vouchers
    path('vouchers/', voucher.voucher_list, name='admin_vouchers'),
    path('vouchers/add/', voucher.voucher_add, name='admin_voucher_add'),
    path('vouchers/edit/<int:pk>/', voucher.voucher_edit, name='admin_voucher_edit'),
    path('vouchers/delete/<int:pk>/', voucher.voucher_delete, name='admin_voucher_delete'),
    path('vouchers/duplicate/<int:pk>/', voucher.voucher_duplicate, name='admin_voucher_duplicate'),
    path('vouchers/assign/', voucher.assign_vouchers_to_users, name='assign_vouchers_to_users'),
    path('vouchers/edit-users/<int:pk>/', voucher.edit_voucher_users, name='edit_voucher_users'),
    path('vouchers/check-code/', voucher.check_voucher_code, name='check_voucher_code'),
    
    # CRM URLs
    path('crm/orders/<int:pk>/', crm.crm_order_detail, name='crm_order_detail'),
    path('crm/packages/', crm.crm_package_list, name='crm_package_list'),
    path('crm/packages/<int:pk>/', crm.crm_package_detail, name='crm_package_detail'),
    path('crm/products/', crm.crm_product_list, name='crm_product_list'),
    path('crm/products/<int:pk>/', crm.crm_product_detail, name='crm_product_detail'),
    
    # FAQ
    path('faq/', faq.faq_list, name='faq_list'),
    path('faq/create/', faq.faq_create, name='faq_create'),
    path('faq/edit/<int:pk>/', faq.faq_edit, name='faq_edit'),
    path('faq/delete/<int:pk>/', faq.faq_delete, name='faq_delete'),
    path('faq/preview/<int:pk>/', faq.faq_preview, name='faq_preview'),
    
    # Loyalty Management URLs
    path('loyalty/dashboard/', loyalty_dashboard, name='loyalty_dashboard'),
    path('loyalty/tiers/', loyalty_tiers_list, name='loyalty_tiers_list'),
    path('loyalty/tiers/create/', loyalty_tier_create, name='loyalty_tier_create'),
    path('loyalty/tiers/<int:tier_id>/edit/', loyalty_tier_edit, name='loyalty_tier_edit'),
    path('loyalty/tiers/<int:tier_id>/delete/', loyalty_tier_delete, name='loyalty_tier_delete'),
    path('loyalty/customers/', loyalty_customers_list, name='loyalty_customers_list'),
    path('loyalty/customers/<int:user_id>/', customer_loyalty_detail, name='customer_loyalty_detail'),
    path('loyalty/customers/<int:user_id>/voucher/create/', create_manual_voucher, name='create_manual_voucher'),
    path('loyalty/vouchers/', loyalty_vouchers_list, name='loyalty_vouchers_list'),
    path('loyalty/settings/', loyalty_settings, name='loyalty_settings'),
    path('loyalty/recalculate/', recalculate_loyalty_tiers_view, name='recalculate_loyalty_tiers'),
]
