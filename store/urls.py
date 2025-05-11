from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views
from django.contrib.admin.views.decorators import staff_member_required

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('category/<slug:slug>/', views.category_detail, name='category_detail'),
    path('add-comment/<int:product_id>/', views.add_comment, name='add_comment'),
    path('register/', views.register, name='register'),
    path('verification-sent/', views.verification_sent, name='verification_sent'),
    path('verify-email/<str:uidb64>/<str:token>/', views.verify_email, name='verify_email'),
    path('cart/', views.cart_detail, name='cart_detail'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('update-cart/<int:item_id>/', views.update_cart, name='update_cart'),
    path('remove-from-cart/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('remove-voucher/', views.remove_voucher, name='remove_voucher'),
    path('my-vouchers/', views.my_vouchers, name='my_vouchers'),
    path('api/search-suggestions/', views.search_suggestions, name='search_suggestions'),
    path('search/', views.search, name='search'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/add-address/', views.add_address, name='add_address'),
    path('profile/edit-address/<int:address_id>/', views.edit_address, name='edit_address'),
    path('profile/delete-address/<int:address_id>/', views.delete_address, name='delete_address'),
    path('profile/set-default-address/<int:address_id>/', views.set_default_address, name='set_default_address'),
    path('profile/cancel-order/<int:order_id>/', views.cancel_order, name='cancel_order'),
    
    # Package URLs
    path('packages/', views.package_list, name='package_list'),
    path('package/<slug:slug>/', views.package_detail, name='package_detail'),
    path('customize-package/<slug:slug>/', views.customize_package, name='customize_package'),
    path('add-package-to-cart/<int:package_id>/', views.add_package_to_cart, name='add_package_to_cart'),
    path('add-customized-package-to-cart/<int:customized_package_id>/', views.add_customized_package_to_cart, name='add_customized_package_to_cart'),
    path('remove-package-from-cart/<int:package_id>/', views.remove_package_from_cart, name='remove_package_from_cart'),
    path('update-package-quantity/<int:cart_package_id>/', views.update_package_quantity, name='update_package_quantity'),
    path('package/<int:package_id>/add-rating/', views.add_package_rating, name='add_package_rating'),
    path('package-rating/<int:rating_id>/edit/', views.edit_package_rating, name='edit_package_rating'),
    path('package-rating/<int:rating_id>/delete/', views.delete_package_rating, name='delete_package_rating'),
    path('add-package-comment/<int:package_id>/', views.add_package_comment, name='add_package_comment'),
    
    # Terms and Conditions
    path('terms-and-conditions/', views.terms_and_conditions, name='terms_and_conditions'),
    
    # FAQ
    path('faq/', views.faq, name='faq'),
    
    # Custom password reset URLs with rate limiting
    path('password-reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
         template_name='registration/password_reset_done.html'), 
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', 
         views.CustomPasswordResetConfirmView.as_view(), 
         name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(
         template_name='registration/password_reset_complete.html'), 
         name='password_reset_complete'),
    path('order/<int:order_id>/bill/', views.order_bill, name='order_bill'),
    path('social-auth-error/', views.social_auth_error, name='social_auth_error'),
    
    # Notification URLs
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/delete/<int:notification_id>/', views.delete_notification, name='delete_notification'),
    path('notifications/unread-count/', views.unread_notifications_count, name='unread_notifications_count'),
    
    # Payment and Checkout URLs
    path('checkout/', views.checkout, name='checkout'),
    path('payment/<int:order_id>/', views.payment, name='payment'),
    path('complete-payment/<int:order_id>/', views.complete_payment, name='complete_payment'),
    path('order-success/<int:order_id>/', views.order_success, name='order_success'),
    path('order-detail/<int:order_id>/', views.order_detail, name='order_detail'),
    path('add-credit-card/', views.add_credit_card, name='add_credit_card'),
    
    # Authentication URLs
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Password change URLs
    path('password-change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(
         template_name='registration/password_change_done.html'), 
         name='password_change_done'),
    
    # Voucher-related URLs
    path('vouchers/', views.my_vouchers, name='my_vouchers'),
    path('add-voucher-to-cart/', views.add_voucher_to_cart, name='add_voucher_to_cart'),
    path('remove-voucher-from-cart/', views.remove_voucher, name='remove_voucher_from_cart'),
    
    # Admin voucher assignment
    path('admin/store/assign-vouchers/', views.assign_vouchers_to_users, name='assign_vouchers'),
    path('admin/store/voucher-guide/', staff_member_required(views.voucher_guide), name='voucher_guide'),
    
    # Product Rating URLs
    path('product/<int:product_id>/add-rating/', views.add_rating, name='add_rating'),
    path('rating/<int:rating_id>/edit/', views.edit_rating, name='edit_rating'),
    path('rating/<int:rating_id>/delete/', views.delete_rating, name='delete_rating'),
]
