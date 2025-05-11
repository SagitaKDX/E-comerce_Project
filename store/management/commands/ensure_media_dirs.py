import os
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Ensures that all required media directories exist'

    def handle(self, *args, **kwargs):
        media_root = settings.MEDIA_ROOT
        
        # Ensure media root exists
        if not os.path.exists(media_root):
            os.makedirs(media_root)
            self.stdout.write(self.style.SUCCESS(f'Created media directory: {media_root}'))
        
        # Define directories to create
        dirs_to_create = [
            'products',
            'categories',
            'banners',
            'order_barcodes',
            'user_profiles',
        ]
        
        # Create each directory if it doesn't exist
        for dir_name in dirs_to_create:
            dir_path = os.path.join(media_root, dir_name)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
                self.stdout.write(self.style.SUCCESS(f'Created media subdirectory: {dir_path}'))
            else:
                self.stdout.write(f'Directory already exists: {dir_path}')
        
        self.stdout.write(self.style.SUCCESS('Media directories setup complete.')) 