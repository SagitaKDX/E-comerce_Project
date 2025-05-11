from django.shortcuts import redirect
from django.contrib import messages
from django.urls import resolve, reverse
from django.contrib.auth import logout

class InactiveUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Code to be executed for each request before the view is called
        if request.user.is_authenticated and not request.user.is_active:
            # Get the current path
            current_url = resolve(request.path_info).url_name
            
            # List of allowed URLs for inactive users
            allowed_urls = ['login', 'logout', 'password_reset', 'password_reset_done', 
                           'password_reset_confirm', 'password_reset_complete']
            
            # If trying to access a non-allowed URL, log them out and redirect
            if current_url not in allowed_urls:
                messages.error(request, "Your account is inactive. Please contact support.")
                logout(request)
                return redirect('login')

        response = self.get_response(request)
        return response 