from django.core.management.base import BaseCommand
from store.models import Package, PackageProduct, Product, Category
from django.utils.text import slugify
import random

class Command(BaseCommand):
    help = 'Create sample packages for testing'

    def handle(self, *args, **options):
        categories = Category.objects.all()
        products = Product.objects.filter(is_active=True)

        if not categories.exists() or not products.exists():
            self.stdout.write(self.style.ERROR('No categories or products found. Please create them first.'))
            return

        package_data = [
            {
                'name': 'Technology Student Package',
                'description': 'Everything a technology student needs for their studies. Includes laptop, headphones, and accessories.',
                'category': 'Electronics',
                'original_price': 1200.00,
                'discounted_price': 950.00,
                'minimum_purchase_amount': 800.00,
                'is_featured': True,
                'products': [
                    {'category': 'Electronics', 'count': 3, 'is_required': [True, False, False]}
                ]
            },
            {
                'name': 'Gaming Setup Package',
                'description': 'Complete gaming setup including gaming peripherals and accessories for the ultimate gaming experience.',
                'category': 'Electronics',
                'original_price': 800.00,
                'discounted_price': 700.00,
                'minimum_purchase_amount': 600.00,
                'is_featured': True,
                'products': [
                    {'category': 'Electronics', 'count': 4, 'is_required': [True, True, False, False]}
                ]
            },
            {
                'name': 'Home Office Bundle',
                'description': 'Everything you need for a productive home office. Includes desk, chair, and accessories.',
                'category': 'Furniture',
                'original_price': 600.00,
                'discounted_price': 550.00,
                'minimum_purchase_amount': 450.00,
                'is_featured': True,
                'products': [
                    {'category': 'Furniture', 'count': 3, 'is_required': [True, False, False]}
                ]
            },
            {
                'name': 'Kitchen Essentials Package',
                'description': 'Essential kitchen tools and appliances for your new home or kitchen renovation.',
                'category': 'Home & Kitchen',
                'original_price': 400.00,
                'discounted_price': 350.00,
                'minimum_purchase_amount': 300.00,
                'is_featured': True,
                'products': [
                    {'category': 'Home & Kitchen', 'count': 5, 'is_required': [True, True, False, False, False]}
                ]
            }
        ]

        packages_created = 0
        
        for package_info in package_data:
            # Try to find the category
            try:
                category = None
                for cat in categories:
                    if package_info['category'].lower() in cat.name.lower():
                        category = cat
                        break
                
                if not category:
                    self.stdout.write(self.style.WARNING(f"Category '{package_info['category']}' not found, using first category"))
                    category = categories.first()
                
                # Check if package with this name already exists
                package_name = package_info['name']
                if Package.objects.filter(name=package_name).exists():
                    self.stdout.write(self.style.WARNING(f"Package '{package_name}' already exists, skipping"))
                    continue
                
                # Create the package
                package = Package.objects.create(
                    name=package_name,
                    slug=slugify(package_name),
                    description=package_info['description'],
                    original_price=package_info['original_price'],
                    discounted_price=package_info['discounted_price'],
                    category=category,
                    minimum_purchase_amount=package_info['minimum_purchase_amount'],
                    is_active=True,
                    is_featured=package_info['is_featured']
                )
                
                # Add products to the package
                for product_info in package_info['products']:
                    product_category = None
                    for cat in categories:
                        if product_info['category'].lower() in cat.name.lower():
                            product_category = cat
                            break
                    
                    if not product_category:
                        product_category = category
                    
                    # Get products from this category
                    category_products = products.filter(category=product_category)
                    if not category_products.exists():
                        self.stdout.write(self.style.WARNING(f"No products found in category '{product_info['category']}', using random products"))
                        # Use random products if no products found in the category
                        selected_products = random.sample(list(products), min(product_info['count'], products.count()))
                    else:
                        # Use products from the category
                        selected_products = random.sample(list(category_products), min(product_info['count'], category_products.count()))
                    
                    # Add products to the package
                    for i, product in enumerate(selected_products):
                        is_required = product_info['is_required'][i] if i < len(product_info['is_required']) else False
                        PackageProduct.objects.create(
                            package=package,
                            product=product,
                            quantity=random.randint(1, 3),
                            is_required=is_required
                        )
                
                packages_created += 1
                self.stdout.write(self.style.SUCCESS(f"Created package '{package.name}' with {package.package_products.count()} products"))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error creating package '{package_info['name']}': {str(e)}"))
        
        self.stdout.write(self.style.SUCCESS(f"Successfully created {packages_created} packages")) 