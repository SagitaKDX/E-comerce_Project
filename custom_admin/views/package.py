from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from store.models import Package, Product, Category, PackageProduct
from custom_admin.views.dashboard import is_admin
from django import forms
from django.utils.text import slugify
from django.db import transaction
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)

class PackageForm(forms.ModelForm):
    class Meta:
        model = Package
        fields = ['name', 'category', 'description', 'original_price', 'discounted_price', 
                 'minimum_purchase_amount', 'image', 'is_active', 'is_featured']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'original_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'discounted_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'minimum_purchase_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'minimum_purchase_amount': 'Minimum amount customers must spend when customizing this package',
            'is_featured': 'Featured packages appear on the home page',
            'discounted_price': 'The price customers will pay for this package',
            'original_price': 'The original/regular price (to show savings)',
        }
    
    def clean(self):
        cleaned_data = super().clean()
        original_price = cleaned_data.get('original_price')
        discounted_price = cleaned_data.get('discounted_price')
        
        if original_price and discounted_price and discounted_price > original_price:
            self.add_error('discounted_price', 'Discounted price cannot be greater than original price')
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Generate a unique slug based on the name
        base_slug = slugify(instance.name)
        instance.slug = base_slug
        
        # Check for existing slugs and make it unique if needed
        if commit:
            counter = 1
            while Package.objects.filter(slug=instance.slug).exclude(pk=instance.pk).exists():
                instance.slug = f"{base_slug}-{counter}"
                counter += 1
            instance.save()
        
        return instance

class PackageProductForm(forms.ModelForm):
    class Meta:
        model = PackageProduct
        fields = ['product', 'quantity', 'is_required']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select product-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'is_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

PackageProductFormSet = inlineformset_factory(
    Package, 
    PackageProduct,
    form=PackageProductForm,
    extra=1,
    can_delete=True
)

@user_passes_test(is_admin, login_url='admin_dashboard:admin_login')
def package_list(request):
    packages = Package.objects.all().order_by('-created')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        packages = packages.filter(name__icontains=search_query)
    
    # Category filter
    category_id = request.GET.get('category', '')
    if category_id and category_id.isdigit():
        packages = packages.filter(category_id=category_id)
    
    # Pagination
    paginator = Paginator(packages, 10)  # Show 10 packages per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    categories = Category.objects.all()
    
    return render(request, 'custom_admin/packages/list.html', {
        'packages': page_obj,
        'categories': categories,
        'search_query': search_query,
        'selected_category': int(category_id) if category_id and category_id.isdigit() else None,
    })

@user_passes_test(is_admin, login_url='admin_dashboard:admin_login')
def package_add(request):
    if request.method == 'POST':
        form = PackageForm(request.POST, request.FILES)
        # Initialize formset without an instance for adding
        formset = PackageProductFormSet(request.POST)
        
        # Use standard validation
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    # Save the main package form first
                    package = form.save()
                    # Associate formset with the saved package and save
                    formset.instance = package
                    formset.save()
                             
                    messages.success(request, f'Package "{package.name}" created successfully.')
                    return redirect('admin_dashboard:admin_packages')
            except Exception as e:
                logger.error(f"[PACKAGE_ADD] Transaction error: {str(e)}")
                messages.error(request, f'Error saving package: {str(e)}')
                             
        else: # Form or Formset is invalid
            # Display main form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
                    
            # Display formset errors (both non-form and form-specific)
            if formset.non_form_errors():
                for error in formset.non_form_errors():
                    messages.error(request, f'Products Error: {error}')
            
            for i, subform in enumerate(formset.forms):
                 # Check if the subform has errors and is not marked for deletion
                 is_deleted = False
                 try:
                     is_deleted = request.POST.get(f'{formset.prefix}-{i}-DELETE') == 'on'
                 except:
                     pass
                 
                 if subform.errors and not is_deleted:
                    for field, error_msgs in subform.errors.items():
                        for error_msg in error_msgs:
                            messages.error(request, f'Product #{i+1} {field}: {error_msg}')        
                    
    else: # GET request
        form = PackageForm()
        # Initialize an empty formset for the add page
        formset = PackageProductFormSet(queryset=PackageProduct.objects.none())
    
    products = Product.objects.filter(is_active=True)
    
    return render(request, 'custom_admin/packages/form.html', {
        'form': form,
        'formset': formset,
        'products': products,
        'title': 'Add Package',
        'is_add': True,
    })

@user_passes_test(is_admin, login_url='admin_dashboard:admin_login')
def package_edit(request, pk):
    package = get_object_or_404(Package, pk=pk)
    
    if request.method == 'POST':
        # --- DEBUGGING: Log raw POST data and management form values --- 
        logger.info(f"[PACKAGE_EDIT POST {pk}] Raw POST data: {request.POST}")
        formset_prefix = 'packageproduct_set' # Assuming default prefix
        logger.info(f"[PACKAGE_EDIT POST {pk}] TOTAL_FORMS: {request.POST.get(f'{formset_prefix}-TOTAL_FORMS')}")
        logger.info(f"[PACKAGE_EDIT POST {pk}] INITIAL_FORMS: {request.POST.get(f'{formset_prefix}-INITIAL_FORMS')}")
        logger.info(f"[PACKAGE_EDIT POST {pk}] MIN_NUM_FORMS: {request.POST.get(f'{formset_prefix}-MIN_NUM_FORMS')}")
        logger.info(f"[PACKAGE_EDIT POST {pk}] MAX_NUM_FORMS: {request.POST.get(f'{formset_prefix}-MAX_NUM_FORMS')}")
        # --- END DEBUGGING ---
        
        form = PackageForm(request.POST, request.FILES, instance=package)
        formset = PackageProductFormSet(request.POST, instance=package)
        
        # Use the standard validation check
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    package = form.save() # Save the main form
                    
                    # Save the formset (handles additions, changes, and deletions)
                    formset.save()
                    
                    messages.success(request, f'Package "{package.name}" updated successfully.')
                    return redirect('admin_dashboard:admin_packages')
            except Exception as e:
                logger.error(f"[PACKAGE_EDIT] Transaction error for package {pk}: {str(e)}")
                messages.error(request, f'Error updating package: {str(e)}')
        else:
            # Display main form errors
            logger.warning(f"[PACKAGE_EDIT {pk}] Form or Formset invalid.") # Log validation failure
            if form.errors:
                 logger.warning(f"[PACKAGE_EDIT {pk}] Main form errors: {form.errors}")
            if formset.errors:
                 logger.warning(f"[PACKAGE_EDIT {pk}] Formset errors: {formset.errors}")
            if formset.non_form_errors():
                 logger.warning(f"[PACKAGE_EDIT {pk}] Formset non-form errors: {formset.non_form_errors()}")
                 
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
            
            # Display formset errors (both non-form and form-specific)
            if formset.non_form_errors():
                for error in formset.non_form_errors():
                    messages.error(request, f'Products Error: {error}')
                    
            for i, subform in enumerate(formset.forms):
                 # Check if the subform has errors and is not marked for deletion
                 is_deleted = False
                 try:
                     is_deleted = request.POST.get(f'{formset.prefix}-{i}-DELETE') == 'on'
                 except:
                     pass
                 
                 if subform.errors and not is_deleted:
                    logger.warning(f"[PACKAGE_EDIT {pk}] Errors in subform #{i}: {subform.errors}") # Log subform errors
                    for field, error_msgs in subform.errors.items():
                        for error_msg in error_msgs:
                            messages.error(request, f'Product #{i+1} {field}: {error_msg}')

    else: # GET request
        form = PackageForm(instance=package)
        formset = PackageProductFormSet(instance=package)
    
    products = Product.objects.filter(is_active=True)
    
    return render(request, 'custom_admin/packages/form.html', {
        'form': form,
        'formset': formset,
        'products': products,
        'package': package,
        'title': 'Edit Package',
        'is_add': False,
    })

@user_passes_test(is_admin, login_url='admin_dashboard:admin_login')
def package_delete(request, pk):
    package = get_object_or_404(Package, pk=pk)
    
    if request.method == 'POST':
        package_name = package.name
        package.delete()
        messages.success(request, f'Package "{package_name}" has been deleted.')
        return redirect('admin_dashboard:admin_packages')
    
    return render(request, 'custom_admin/packages/delete.html', {
        'package': package,
    }) 