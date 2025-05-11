"""
URL configuration for ecommerce_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from store.views import social_auth_error, api_notifications, api_mark_all_notifications_read
from store.admin import admin_site as custom_admin_site

urlpatterns = [
    # Django admin
    path('admin/', custom_admin_site.urls),
    
    # Custom admin - no explicit namespace here since it's defined in urls.py with app_name
    path('custom-admin/', include('custom_admin.urls')),
    
    # Store URLs - place before Django auth URLs to override default authentication patterns
    path('', include('store.urls')),
    
    # Remove Django auth URLs as they're already included in store.urls
    # path('accounts/', include('django.contrib.auth.urls')),

    # Social Auth URLs
    path('social-auth/', include('social_django.urls', namespace='social')),
    path('social-auth/error/', social_auth_error, name='social_auth_error'),

    # CRM URLs - placeholder to avoid errors
    path('crm/', include('custom_admin.crm_urls')),
    
    # Live Chat URLs
    path('livechat/', include('livechat.urls')),

    # Add these API URLs in the urlpatterns list
    path('api/notifications/', api_notifications, name='api_notifications'),
    path('api/notifications/mark-all-read/', api_mark_all_notifications_read, name='api_mark_all_notifications_read'),
]

# Always add media URL pattern, even outside of debug for development environments
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


