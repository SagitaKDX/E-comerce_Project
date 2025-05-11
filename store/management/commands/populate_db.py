from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from store.models import Category, Product
from django.utils.text import slugify
import random
import os
from django.conf import settings
import shutil
from django.core.files import File

class Command(BaseCommand):
    help = 'Populate database with sample data'

    def handle(self, *args, **options):
        # Create categories
        categories = [
            'Electronics',
            'Clothing',
            'Books',
            'Home & Kitchen',
            'Sports & Outdoors',
        ]
        
        for category_name in categories:
            Category.objects.get_or_create(
                name=category_name,
                slug=slugify(category_name)
            )
            self.stdout.write(self.style.SUCCESS(f'Created category: {category_name}'))
        
        # Create products
        electronics = Category.objects.get(name='Electronics')
        clothing = Category.objects.get(name='Clothing')
        books = Category.objects.get(name='Books')
        home = Category.objects.get(name='Home & Kitchen')
        sports = Category.objects.get(name='Sports & Outdoors')
        
        products = [
            {
                'name': 'Smartphone X',
                'category': electronics,
                'price': 699.99,
                'description': 'Latest smartphone with high-resolution camera and long battery life.',
                'stock': 50
            },
            {
                'name': 'Laptop Pro',
                'category': electronics,
                'price': 1299.99,
                'description': 'Powerful laptop for professionals with high-end specifications.',
                'stock': 25
            },
            {
                'name': 'Wireless Headphones',
                'category': electronics,
                'price': 149.99,
                'description': 'Noise-cancelling wireless headphones with premium sound quality.',
                'stock': 100
            },
            {
                'name': 'Men\'s T-Shirt',
                'category': clothing,
                'price': 24.99,
                'description': 'Comfortable cotton t-shirt available in multiple colors.',
                'stock': 200
            },
            {
                'name': 'Women\'s Jeans',
                'category': clothing,
                'price': 49.99,
                'description': 'Stylish and durable jeans for everyday wear.',
                'stock': 150
            },
            {
                'name': 'Python Programming',
                'category': books,
                'price': 39.99,
                'description': 'Comprehensive guide to Python programming for beginners and advanced users.',
                'stock': 75
            },
            {
                'name': 'Cooking Essentials',
                'category': books,
                'price': 29.99,
                'description': 'Learn the essential cooking techniques and recipes.',
                'stock': 60
            },
            {
                'name': 'Coffee Maker',
                'category': home,
                'price': 89.99,
                'description': 'Automatic coffee maker with timer and multiple brewing options.',
                'stock': 40
            },
            {
                'name': 'Blender',
                'category': home,
                'price': 69.99,
                'description': 'High-powered blender for smoothies, soups, and more.',
                'stock': 35
            },
            {
                'name': 'Yoga Mat',
                'category': sports,
                'price': 29.99,
                'description': 'Non-slip yoga mat for comfortable workouts.',
                'stock': 120
            },
            {
                'name': 'Dumbbell Set',
                'category': sports,
                'price': 119.99,
                'description': 'Adjustable dumbbell set for home workouts.',
                'stock': 25
            },
            {
                'name': 'Smart Watch',
                'category': electronics,
                'price': 249.99,
                'description': 'Track your fitness, receive notifications, and more with this smart watch.',
                'stock': 60
            },
            {
                'name': 'Winter Jacket',
                'category': clothing,
                'price': 129.99,
                'description': 'Warm and water-resistant jacket for cold weather.',
                'stock': 80
            },
            {
                'name': 'Data Science Handbook',
                'category': books,
                'price': 45.99,
                'description': 'Comprehensive guide to data science techniques and tools.',
                'stock': 40
            },
            {
                'name': 'Air Fryer',
                'category': home,
                'price': 99.99,
                'description': 'Cook healthier meals with little to no oil.',
                'stock': 30
            },
            {
                'name': 'Tennis Racket',
                'category': sports,
                'price': 89.99,
                'description': 'Professional-grade tennis racket for all skill levels.',
                'stock': 45
            },
        ]
        
        # Create sample product images directory if it doesn't exist
        sample_images_dir = os.path.join(settings.BASE_DIR, 'sample_images')
        os.makedirs(sample_images_dir, exist_ok=True)
        
        # Create placeholder images for products
        for i, product_data in enumerate(products):
            product_name = product_data['name']
            slug = slugify(product_name)
            
            # Check if product already exists
            if Product.objects.filter(slug=slug).exists():
                self.stdout.write(self.style.WARNING(f'Product already exists: {product_name}'))
                continue
            
            # Create a placeholder image
            image_path = os.path.join(sample_images_dir, f'product_{i+1}.jpg')
            
            # Create a simple colored image using PIL
            try:
                from PIL import Image, ImageDraw
                
                # Create a colored rectangle with product name
                img = Image.new('RGB', (800, 600), color=(random.randint(100, 255), 
                                                          random.randint(100, 255), 
                                                          random.randint(100, 255)))
                d = ImageDraw.Draw(img)
                d.text((400, 300), product_name, fill=(255, 255, 255))
                img.save(image_path)
                
                # Create the product with the image
                product = Product.objects.create(
                    name=product_name,
                    slug=slug,
                    category=product_data['category'],
                    price=product_data['price'],
                    description=product_data['description'],
                    stock=product_data['stock'],
                    available=True
                )
                
                # Add the image to the product
                with open(image_path, 'rb') as img_file:
                    product.image.save(f'{slug}.jpg', File(img_file), save=True)
                
                self.stdout.write(self.style.SUCCESS(f'Created product: {product_name}'))
            
            except ImportError:
                self.stdout.write(self.style.WARNING('PIL not installed. Skipping image creation.'))
                
                # Create the product without an image
                product = Product.objects.create(
                    name=product_name,
                    slug=slug,
                    category=product_data['category'],
                    price=product_data['price'],
                    description=product_data['description'],
                    stock=product_data['stock'],
                    available=True
                )
                
                self.stdout.write(self.style.SUCCESS(f'Created product (no image): {product_name}'))
        
        # Create a test user
        if not User.objects.filter(username='testuser').exists():
            User.objects.create_user(
                username='testuser',
                email='test@example.com',
                password='testpassword123',
                first_name='Test',
                last_name='User'
            )
            self.stdout.write(self.style.SUCCESS('Created test user: testuser / testpassword123'))
        
        # Clean up
        if os.path.exists(sample_images_dir):
            shutil.rmtree(sample_images_dir)
        
        self.stdout.write(self.style.SUCCESS('Database populated successfully!'))
