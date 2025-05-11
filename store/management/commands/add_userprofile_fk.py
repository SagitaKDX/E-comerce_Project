from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Adds missing foreign key constraint to UserProfile table'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # Check if constraint exists first
            cursor.execute("""
                SELECT CONSTRAINT_NAME 
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'store_userprofile'
                AND COLUMN_NAME = 'user_id'
                AND REFERENCED_TABLE_NAME = 'auth_user'
            """)
            constraint = cursor.fetchone()
            
            if constraint:
                self.stdout.write(self.style.SUCCESS(f"Foreign key constraint already exists: {constraint[0]}"))
            else:
                self.stdout.write(self.style.WARNING("Adding foreign key constraint to store_userprofile..."))
                
                # First check if there's a unique index on user_id
                cursor.execute("""
                    SHOW INDEXES FROM store_userprofile
                    WHERE Column_name = 'user_id' AND Non_unique = 0
                """)
                unique_index = cursor.fetchone()
                
                if not unique_index:
                    self.stdout.write(self.style.WARNING("Adding unique index on user_id..."))
                    cursor.execute("""
                        ALTER TABLE store_userprofile
                        ADD UNIQUE INDEX idx_unique_user_id (user_id)
                    """)
                    self.stdout.write(self.style.SUCCESS("Added unique index on user_id"))
                
                # Now add the foreign key constraint
                try:
                    cursor.execute("""
                        ALTER TABLE store_userprofile 
                        ADD CONSTRAINT fk_store_userprofile_user 
                        FOREIGN KEY (user_id) 
                        REFERENCES auth_user (id) 
                        ON DELETE CASCADE
                    """)
                    self.stdout.write(self.style.SUCCESS("Foreign key constraint added successfully"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error adding foreign key constraint: {str(e)}"))
            
            # Verify the constraints now
            cursor.execute("""
                SELECT CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'store_userprofile'
                AND REFERENCED_TABLE_NAME IS NOT NULL
            """)
            constraints = cursor.fetchall()
            
            if constraints:
                self.stdout.write(self.style.SUCCESS("\nCurrent foreign key constraints:"))
                for c in constraints:
                    self.stdout.write(f"  - {c[0]}: {c[1]} -> {c[2]}.{c[3]}")
            else:
                self.stdout.write(self.style.WARNING("\nNo foreign key constraints found after update!"))
        
        self.stdout.write(self.style.SUCCESS("Foreign key check completed")) 