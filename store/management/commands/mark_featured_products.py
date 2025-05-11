from django.core.management.base import BaseCommand
from store.models import Product

class Command(BaseCommand):
    help = 'Mark products as featured'

    def handle(self, *args, **options):
        products = Product.objects.all()[:8]
        count = 0
        for product in products:
            product.is_featured = True
            product.save()
            count += 1
        
        self.stdout.write(self.style.SUCCESS(f'Successfully marked {count} products as featured')) 