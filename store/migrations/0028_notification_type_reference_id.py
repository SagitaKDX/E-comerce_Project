# Generated manually to fix migration issues

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0027_remove_cart_voucher_remove_order_notes_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(choices=[('order', 'Order'), ('payment', 'Payment'), ('system', 'System'), ('promo', 'Promotion')], default='system', max_length=20),
        ),
        migrations.AddField(
            model_name='notification',
            name='reference_id',
            field=models.IntegerField(blank=True, help_text='ID of the referenced object (e.g., order ID)', null=True),
        ),
    ] 