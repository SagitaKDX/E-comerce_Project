from django.core.management.base import BaseCommand
from django.db import connection
from django.contrib.auth.models import User
from store.models import UserProfile
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Comprehensive database check and repair tool'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # 1. First check auth_user vs auth_user column types
            self.stdout.write(self.style.NOTICE("Checking auth_user table structure..."))
            cursor.execute("DESCRIBE auth_user")
            auth_user_columns = cursor.fetchall()
            auth_user_id_type = None
            for col in auth_user_columns:
                if col[0] == 'id':
                    auth_user_id_type = col[1]
                    self.stdout.write(f"auth_user.id type: {auth_user_id_type}")
            
            # 2. Check store_userprofile.user_id type
            self.stdout.write(self.style.NOTICE("Checking store_userprofile table structure..."))
            cursor.execute("DESCRIBE store_userprofile")
            userprofile_columns = cursor.fetchall()
            user_id_type = None
            for col in userprofile_columns:
                if col[0] == 'user_id':
                    user_id_type = col[1]
                    self.stdout.write(f"store_userprofile.user_id type: {user_id_type}")
            
            # 3. Check if types match
            if auth_user_id_type != user_id_type and auth_user_id_type and user_id_type:
                self.stdout.write(self.style.WARNING(f"Column type mismatch! auth_user.id: {auth_user_id_type}, store_userprofile.user_id: {user_id_type}"))
                
                # Fix type mismatch
                self.stdout.write(self.style.WARNING(f"Altering store_userprofile.user_id to match auth_user.id..."))
                cursor.execute(f"ALTER TABLE store_userprofile MODIFY user_id {auth_user_id_type}")
                self.stdout.write(self.style.SUCCESS(f"Column type updated"))
            
            # 4. Check relationships
            self.stdout.write(self.style.NOTICE("Checking relationships between users and profiles..."))
            cursor.execute("""
                SELECT u.id, u.username, u.email, p.id 
                FROM auth_user u
                LEFT JOIN store_userprofile p ON u.id = p.user_id
            """)
            user_relationships = cursor.fetchall()
            
            users_missing_profiles = []
            
            self.stdout.write(self.style.SUCCESS(f"User-profile relationships:"))
            for user_id, username, email, profile_id in user_relationships:
                status = "OK" if profile_id else "MISSING PROFILE"
                self.stdout.write(f"  - User {username} (ID: {user_id}): {status}")
                if not profile_id:
                    users_missing_profiles.append((user_id, username, email))
            
            # 5. Create missing profiles
            if users_missing_profiles:
                self.stdout.write(self.style.WARNING(f"Found {len(users_missing_profiles)} users with missing profiles"))
                for user_id, username, email in users_missing_profiles:
                    self.stdout.write(f"Creating profile for user {username}...")
                    try:
                        user = User.objects.get(id=user_id)
                        UserProfile.objects.create(
                            user=user,
                            role='customer'
                        )
                        self.stdout.write(self.style.SUCCESS(f"Profile created for {username}"))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error creating profile: {str(e)}"))
            
            # 6. Try to add foreign key constraint manually
            try:
                # First ensure unique index
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
                
                # Check if constraint already exists
                cursor.execute("""
                    SELECT CONSTRAINT_NAME 
                    FROM information_schema.KEY_COLUMN_USAGE
                    WHERE TABLE_SCHEMA = DATABASE()
                    AND TABLE_NAME = 'store_userprofile'
                    AND COLUMN_NAME = 'user_id'
                    AND REFERENCED_TABLE_NAME = 'auth_user'
                """)
                constraint = cursor.fetchone()
                
                if not constraint:
                    # Add the constraint
                    self.stdout.write(self.style.WARNING("Adding foreign key constraint..."))
                    cursor.execute("""
                        ALTER TABLE store_userprofile 
                        ADD CONSTRAINT fk_store_userprofile_user 
                        FOREIGN KEY (user_id) 
                        REFERENCES auth_user (id)
                    """)
                    self.stdout.write(self.style.SUCCESS("Foreign key constraint added"))
                else:
                    self.stdout.write(self.style.SUCCESS(f"Foreign key constraint already exists: {constraint[0]}"))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error fixing constraint: {str(e)}"))
                
            # 7. Clean up unused tables
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                AND table_name IN ('user_profile', 'user_profile_old')
            """)
            unused_tables = [row[0] for row in cursor.fetchall()]
            
            for table in unused_tables:
                self.stdout.write(self.style.WARNING(f"Dropping unused table: {table}"))
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                self.stdout.write(self.style.SUCCESS(f"Dropped table: {table}"))
        
        self.stdout.write(self.style.SUCCESS("Database repair completed")) 