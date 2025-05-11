# custom_admin/views/category.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from store.models import Category
from custom_admin.views.dashboard import is_admin
from django import forms
from django.utils.text import slugify

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'image']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
        }

@user_passes_test(is_admin, login_url='custom_admin:admin_login')
def category_list(request):
    categories = Category.objects.all().order_by('name')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        categories = categories.filter(name__icontains=search_query)
    
    # Pagination
    paginator = Paginator(categories, 20)  # Show 20 categories per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'custom_admin/categories/list.html', {
        'categories': page_obj,
        'search_query': search_query,
    })

@user_passes_test(is_admin, login_url='custom_admin:admin_login')
def category_add(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            category = form.save(commit=False)
            if not category.slug:
                category.slug = slugify(category.name)
            category.save()
            messages.success(request, f'Category "{category.name}" created successfully.')
            return redirect('admin_dashboard:admin_categories')
    else:
        form = CategoryForm()
    
    return render(request, 'custom_admin/categories/form.html', {
        'form': form,
        'title': 'Add Category',
        'is_add': True,
    })

@user_passes_test(is_admin, login_url='custom_admin:admin_login')
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f'Category "{category.name}" updated successfully.')
            return redirect('admin_dashboard:admin_categories')
    else:
        form = CategoryForm(instance=category)
    
    return render(request, 'custom_admin/categories/form.html', {
        'form': form,
        'category': category,
        'title': 'Edit Category',
        'is_add': False,
    })

@user_passes_test(is_admin, login_url='custom_admin:admin_login')
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    
    if request.method == 'POST':
        category_name = category.name
        category.delete()
        messages.success(request, f'Category "{category_name}" deleted successfully.')
        return redirect('admin_dashboard:admin_categories')
    
    return render(request, 'custom_admin/categories/delete.html', {
        'category': category,
    })
