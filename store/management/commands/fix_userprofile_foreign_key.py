from django.core.management.base import BaseCommand
from django.db import connection
from django.apps import apps
from django.contrib.auth.models import User
from store.models import UserProfile

class Command(BaseCommand):
    help = 'Fixes foreign key issue in UserProfile table'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # Check UserProfile schema
            cursor.execute("DESCRIBE store_userprofile")
            columns = cursor.fetchall()
            column_names = [col[0] for col in columns]
            
            self.stdout.write(self.style.SUCCESS("Current UserProfile schema:"))
            for column in columns:
                self.stdout.write(f"  - {column[0]}: {column[1]}")
            
            # Check if user_id exists
            user_id_exists = 'user_id' in column_names
            
            if not user_id_exists:
                self.stdout.write(self.style.ERROR("user_id column is missing - checking constraints"))
                
                # Check constraints
                cursor.execute("""
                    SELECT CONSTRAINT_NAME, TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                    FROM information_schema.KEY_COLUMN_USAGE
                    WHERE TABLE_SCHEMA = DATABASE()
                    AND TABLE_NAME = 'store_userprofile'
                    AND REFERENCED_TABLE_NAME IS NOT NULL
                """)
                constraints = cursor.fetchall()
                
                if constraints:
                    self.stdout.write(self.style.SUCCESS("Found existing constraints:"))
                    for c in constraints:
                        self.stdout.write(f"  - {c[0]}: {c[1]}.{c[2]} -> {c[3]}.{c[4]}")
                else:
                    self.stdout.write(self.style.WARNING("No foreign key constraints found"))
                    
            # Get current User-UserProfile relationships
            users_with_profiles = []
            for user in User.objects.all():
                try:
                    profile = UserProfile.objects.get(user=user)
                    users_with_profiles.append((user.id, profile.id))
                except UserProfile.DoesNotExist:
                    pass
                    
            self.stdout.write(self.style.SUCCESS(f"Found {len(users_with_profiles)} user-profile relationships"))
            
            # Create a new migration file to fix the issue
            self.stdout.write(self.style.SUCCESS(
                "To fix the foreign key issue, run the following command:\n" +
                "python manage.py makemigrations store --name fix_userprofile_foreign_key"
            ))
                
            # Perform checks on the database schema
            cursor.execute("""
                SELECT table_name, table_rows
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                AND table_name LIKE 'store_%'
                ORDER BY table_name
            """)
            tables = cursor.fetchall()
            
            self.stdout.write(self.style.SUCCESS("\nStore app tables:"))
            for table_name, row_count in tables:
                self.stdout.write(f"  - {table_name}: ~{row_count} rows")
            
        self.stdout.write(self.style.SUCCESS("Schema check completed")) 