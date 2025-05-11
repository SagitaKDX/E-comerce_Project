from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Fixes missing columns in social auth tables'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # Check if 'created' column exists in social_auth_usersocialauth
            cursor.execute("SHOW COLUMNS FROM social_auth_usersocialauth LIKE 'created'")
            created_exists = cursor.fetchone() is not None
            
            if not created_exists:
                self.stdout.write(self.style.WARNING("Adding 'created' column to social_auth_usersocialauth"))
                cursor.execute("ALTER TABLE social_auth_usersocialauth ADD COLUMN created datetime(6) DEFAULT CURRENT_TIMESTAMP(6)")
                self.stdout.write(self.style.SUCCESS("Added 'created' column"))
            else:
                self.stdout.write(self.style.SUCCESS("'created' column already exists"))
                
            # Add other required checks and columns
            self.check_and_add_column(cursor, "social_auth_usersocialauth", "modified", "datetime(6) DEFAULT CURRENT_TIMESTAMP(6)")
            
        self.stdout.write(self.style.SUCCESS('Social auth tables fixed successfully'))
    
    def check_and_add_column(self, cursor, table, column, definition):
        cursor.execute(f"SHOW COLUMNS FROM {table} LIKE '{column}'")
        exists = cursor.fetchone() is not None
        
        if not exists:
            self.stdout.write(self.style.WARNING(f"Adding '{column}' column to {table}"))
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            self.stdout.write(self.style.SUCCESS(f"Added '{column}' column"))
        else:
            self.stdout.write(self.style.SUCCESS(f"'{column}' column already exists")) 