from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('store', '0015_merge_20250404_1035'),
    ]

    operations = [
        # This is a dummy migration to fix the conflicting wishlist migrations
        # The wishlist field should already be removed, but this ensures consistency in the migration graph
    ] 