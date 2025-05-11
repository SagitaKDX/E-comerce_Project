from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Cleans up database by removing unused tables and checking schema'

    def handle(self, *args, **options):
        # Drop the user_profile table if it exists
        with connection.cursor() as cursor:
            # Check if user_profile table exists
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE() 
                AND table_name = 'user_profile'
            """)
            user_profile_exists = cursor.fetchone()[0] > 0
            
            # Drop user_profile table if it exists
            if user_profile_exists:
                self.stdout.write(self.style.WARNING("Dropping user_profile table..."))
                cursor.execute("DROP TABLE IF EXISTS user_profile")
                self.stdout.write(self.style.SUCCESS("Dropped user_profile table successfully"))
            else:
                self.stdout.write(self.style.SUCCESS("No user_profile table found - already cleaned up"))
            
            # Check if user_profile_old table exists and drop it
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE() 
                AND table_name = 'user_profile_old'
            """)
            user_profile_old_exists = cursor.fetchone()[0] > 0
            
            if user_profile_old_exists:
                self.stdout.write(self.style.WARNING("Dropping user_profile_old table..."))
                cursor.execute("DROP TABLE IF EXISTS user_profile_old")
                self.stdout.write(self.style.SUCCESS("Dropped user_profile_old table successfully"))
            
            # Check current schema structure
            self.stdout.write(self.style.NOTICE("Checking database schema..."))
            
            # Check UserProfile structure
            cursor.execute("DESCRIBE store_userprofile")
            columns = cursor.fetchall()
            self.stdout.write(self.style.SUCCESS("UserProfile schema:"))
            for column in columns:
                self.stdout.write(f"  - {column[0]}: {column[1]}")
            
            # Verify foreign key constraints
            cursor.execute("""
                SELECT 
                    TABLE_NAME, COLUMN_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                FROM
                    INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE
                    REFERENCED_TABLE_SCHEMA = DATABASE()
                    AND TABLE_NAME = 'store_userprofile';
            """)
            fks = cursor.fetchall()
            if fks:
                self.stdout.write(self.style.SUCCESS("UserProfile foreign keys:"))
                for fk in fks:
                    self.stdout.write(f"  - {fk[1]} -> {fk[3]}.{fk[4]}")
            else:
                self.stdout.write(self.style.WARNING("No foreign keys found for UserProfile"))
        
        self.stdout.write(self.style.SUCCESS("Database cleanup and schema check completed")) 