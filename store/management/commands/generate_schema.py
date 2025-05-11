from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Generates SQL schema for the entire database'

    def handle(self, *args, **options):
        try:
            # Get all tables in the database
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE()
                    ORDER BY table_name
                """)
                tables = [row[0] for row in cursor.fetchall()]
                
                schema = []
                for table in tables:
                    # Get CREATE TABLE statement
                    cursor.execute(f"SHOW CREATE TABLE `{table}`")
                    create_statement = cursor.fetchone()[1]
                    schema.append(create_statement + ";")
                
                # Write schema to file
                with open("ecommerce_db_schema.sql", "w") as f:
                    f.write("\n\n".join(schema))
                
                self.stdout.write(self.style.SUCCESS(f"Schema for {len(tables)} tables written to ecommerce_db_schema.sql"))
                
                # Also display table list with column count
                self.stdout.write(self.style.NOTICE("\nDatabase Tables:"))
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = '{table}'")
                    column_count = cursor.fetchone()[0]
                    
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    row_count = cursor.fetchone()[0]
                    
                    self.stdout.write(f"  - {table}: {column_count} columns, {row_count} rows")
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error generating schema: {str(e)}")) 