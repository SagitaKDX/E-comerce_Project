from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseRedirect

def admin_required(view_func):
    """
    Decorator that checks if the user is an admin.
    If not, redirects to the login page with an error message.
    """
    def wrapper(request, *args, **kwargs):
        if request.user.is_staff or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        else:
            messages.error(request, "You do not have permission to access the admin area.")
            return HttpResponseRedirect('/')
    return wrapper 