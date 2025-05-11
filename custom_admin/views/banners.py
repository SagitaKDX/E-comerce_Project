from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from store.models import PromoBanner
from ..decorators import admin_required
from ..forms import PromoBannerForm
import csv
from django.http import HttpResponse
from django.utils import timezone
from django.db import models

@login_required
@admin_required
def banner_list(request):
    banners = PromoBanner.objects.all().order_by('order', '-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    today = timezone.now().date()
    
    if status_filter == 'active':
        # Active banners: active=True, start_date <= today or null, end_date >= today or null
        banners = banners.filter(active=True)
        banners = banners.filter(
            (models.Q(start_date__isnull=True) | models.Q(start_date__lte=today)) &
            (models.Q(end_date__isnull=True) | models.Q(end_date__gte=today))
        )
    elif status_filter == 'upcoming':
        # Upcoming banners: active=True, start_date > today
        banners = banners.filter(active=True, start_date__gt=today)
    elif status_filter == 'expired':#
        banners = banners.filter(active=True, end_date__lt=today)
    elif status_filter == 'inactive':
        banners = banners.filter(active=False)
    
    if 'download' in request.GET:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="banners_{status_filter or "all"}_{today}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['ID', 'Title', 'Subtitle', 'Status', 'Start Date', 'End Date', 'Link Type', 'Created At'])
        
        for banner in banners:
            writer.writerow([
                banner.id,
                banner.title,
                banner.subtitle,
                banner.get_status(),
                banner.start_date or 'N/A',
                banner.end_date or 'N/A',
                banner.get_link_type_display(),
                banner.created_at.strftime('%Y-%m-%d')
            ])
        
        return response
    
    paginator = Paginator(banners, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'custom_admin/banners/list.html', {
        'page_obj': page_obj,
        'title': 'Promotional Banners',
        'status_filter': status_filter,
    })

@login_required
@admin_required
def banner_add(request):
    if request.method == 'POST':
        form = PromoBannerForm(request.POST, request.FILES)
        if form.is_valid():
            banner = form.save()
            messages.success(request, f'Banner "{banner.title}" has been added successfully. The homepage will show this banner immediately for new visitors.')
            
            try:
                from django.core.cache import cache
                cache.delete('homepage_banners')
            except:
                pass
                
            return redirect('admin_dashboard:admin_banners')
    else:
        form = PromoBannerForm()
    
    return render(request, 'custom_admin/banners/form.html', {
        'form': form,
        'title': 'Add Promotional Banner',
        'button_text': 'Add Banner',
        'now': timezone.now(),
    })

@login_required
@admin_required
def banner_edit(request, pk=None):
    """Edit an existing banner"""
    banner = get_object_or_404(PromoBanner, id=pk)
    
    if request.method == 'POST':
        form = PromoBannerForm(request.POST, request.FILES, instance=banner)
        if form.is_valid():
            if 'image' in request.FILES or not banner.image:
                banner = form.save()
            else:
                banner = form.save(commit=False)
                banner.save()
            
            try:
                from django.core.cache import cache
                cache.delete('homepage_banners')
            except:
                pass
                
            messages.success(request, f'Banner "{banner.title}" has been updated successfully. The homepage will reflect these changes immediately for new visitors.')
            return redirect('admin_dashboard:admin_banners')
    else:
        form = PromoBannerForm(instance=banner)
    
    return render(request, 'custom_admin/banners/form.html', {
        'form': form,
        'banner': banner,
        'title': 'Edit Promotional Banner',
        'button_text': 'Update Banner',
        'now': timezone.now(),
    })

@login_required
@admin_required
def banner_delete(request, banner_id):
    banner = get_object_or_404(PromoBanner, id=banner_id)
    
    if request.method == 'POST':
        title = banner.title
        banner.delete()
        
        try:
            from django.core.cache import cache
            cache.delete('homepage_banners')
        except:
            pass
            
        messages.success(request, f'Banner "{title}" has been deleted successfully. The banner will be immediately removed from the homepage for new visitors.')
        return redirect('admin_dashboard:admin_banners')
    
    return render(request, 'custom_admin/banners/delete.html', {
        'banner': banner,
        'title': 'Delete Promotional Banner',
    })

@login_required
@admin_required
def banner_reorder(request):
    if request.method == 'POST':
        banner_ids = request.POST.getlist('banner_ids[]')
        
        for index, banner_id in enumerate(banner_ids):
            banner = PromoBanner.objects.get(id=banner_id)
            banner.order = index
            banner.save()
        
        return redirect('admin_dashboard:admin_banners')
    
    banners = PromoBanner.objects.all().order_by('order', '-created_at')
    return render(request, 'custom_admin/banners/reorder.html', {
        'banners': banners,
        'title': 'Reorder Promotional Banners',
    }) 