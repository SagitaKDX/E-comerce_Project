from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Fixes missing columns in the database'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # Define columns to check for PromoBanner
            promobanner_columns = {
                'start_date': 'date NULL',
                'end_date': 'date NULL',
                'button_style': "varchar(20) NOT NULL DEFAULT 'btn-primary'",
                'text_color': "varchar(20) NOT NULL DEFAULT 'text-white'",
                'caption_position': "varchar(10) NOT NULL DEFAULT 'center'",
                'overlay_opacity': "float NOT NULL DEFAULT 0.4"
            }
            
            # Check and add each column
            for column_name, column_def in promobanner_columns.items():
                cursor.execute(f"SHOW COLUMNS FROM store_promobanner LIKE '{column_name}'")
                column_exists = cursor.fetchone() is not None
                
                if not column_exists:
                    self.stdout.write(self.style.WARNING(f'Adding {column_name} column to store_promobanner'))
                    cursor.execute(f"ALTER TABLE store_promobanner ADD COLUMN {column_name} {column_def}")
                    self.stdout.write(self.style.SUCCESS(f'Added {column_name} column'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'{column_name} column already exists'))
        
        self.stdout.write(self.style.SUCCESS('Database columns fixed successfully')) 