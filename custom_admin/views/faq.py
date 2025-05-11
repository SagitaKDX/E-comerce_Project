from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from custom_admin.models import FAQ
from custom_admin.forms.faq_forms import FAQForm
from custom_admin.decorators import admin_required
import logging

# Set up logger
logger = logging.getLogger(__name__)

@login_required
@admin_required
def faq_list(request):
    search_term = request.GET.get('search', '')
    
    # Filter FAQs based on search term
    if search_term:
        faqs = FAQ.objects.filter(
            Q(title__icontains=search_term) | Q(content__icontains=search_term)
        ).order_by('order', 'title')
    else:
        faqs = FAQ.objects.all().order_by('order', 'title')
    
    # Pagination
    paginator = Paginator(faqs, 10)  # Show 10 FAQs per page
    page_number = request.GET.get('page', 1)
    faqs_page = paginator.get_page(page_number)
    
    return render(request, 'custom_admin/faq/list.html', {
        'faqs': faqs_page,
        'search_term': search_term,
    })

@login_required
@admin_required
def faq_create(request):
    logger.info("FAQ create view called with method: %s", request.method)

    if request.method == 'POST':
        logger.info("Processing POST request for FAQ creation")
        form = FAQForm(request.POST)
        
        # Log POST data for debugging (exclude sensitive data)
        logger.info("POST data: %s", {k: v for k, v in request.POST.items() if k != 'csrfmiddlewaretoken'})
        
        if form.is_valid():
            logger.info("Form is valid, saving FAQ")
            try:
                faq = form.save()
                logger.info("FAQ saved successfully with ID: %s", faq.id)
                messages.success(request, 'FAQ created successfully!')
                return redirect('admin_dashboard:faq_list')
            except Exception as e:
                logger.error("Error saving FAQ: %s", str(e))
                messages.error(request, f'Error creating FAQ: {str(e)}')
        else:
            logger.warning("Form validation failed with errors: %s", form.errors)
            messages.warning(request, 'Please correct the errors below.')
    else:
        logger.info("Displaying empty FAQ form")
        form = FAQForm()
    
    return render(request, 'custom_admin/faq/form.html', {
        'form': form,
        'title': 'Create FAQ',
        'submit_text': 'Create',
    })

@login_required
@admin_required
def faq_edit(request, pk):
    faq = get_object_or_404(FAQ, pk=pk)
    
    if request.method == 'POST':
        form = FAQForm(request.POST, instance=faq)
        if form.is_valid():
            form.save()
            messages.success(request, 'FAQ updated successfully!')
            return redirect('admin_dashboard:faq_list')
    else:
        form = FAQForm(instance=faq)
    
    return render(request, 'custom_admin/faq/form.html', {
        'form': form,
        'faq': faq,
        'title': 'Edit FAQ',
        'submit_text': 'Update',
    })

@login_required
@admin_required
def faq_delete(request, pk):
    faq = get_object_or_404(FAQ, pk=pk)
    
    if request.method == 'POST':
        faq.delete()
        messages.success(request, 'FAQ deleted successfully!')
        return redirect('admin_dashboard:faq_list')
    
    return render(request, 'custom_admin/faq/delete.html', {
        'faq': faq,
    })

@login_required
@admin_required
def faq_preview(request, pk):
    faq = get_object_or_404(FAQ, pk=pk)
    return render(request, 'custom_admin/faq/preview.html', {
        'faq': faq,
    }) 