from django.db import migrations

class Migration(migrations.Migration):
    """
    This migration checks if the staff_reviewed columns exist before trying to add them
    """

    dependencies = [
        ('store', '0048_fix_migration_conflict'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            SELECT COUNT(*) INTO @column_exists 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'store_productrating' 
            AND COLUMN_NAME = 'staff_reviewed';
            
            SET @sql = IF(@column_exists = 0, 
                         'ALTER TABLE store_productrating ADD COLUMN staff_reviewed BOOL NOT NULL DEFAULT FALSE',
                         'SELECT 1');
            
            PREPARE stmt FROM @sql;
            EXECUTE stmt;
            DEALLOCATE PREPARE stmt;
            
            SELECT COUNT(*) INTO @column_exists 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'store_packagerating' 
            AND COLUMN_NAME = 'staff_reviewed';
            
            SET @sql = IF(@column_exists = 0, 
                         'ALTER TABLE store_packagerating ADD COLUMN staff_reviewed BOOL NOT NULL DEFAULT FALSE',
                         'SELECT 1');
            
            PREPARE stmt FROM @sql;
            EXECUTE stmt;
            DEALLOCATE PREPARE stmt;
            """,
            reverse_sql="SELECT 1" # Don't do anything on migration reversal
        ),
    ] 