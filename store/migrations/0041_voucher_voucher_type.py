# Generated by Django 5.1.6 on 2025-04-04 09:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0040_alter_cart_active_voucher_alter_order_voucher'),
    ]

    operations = [
        migrations.AddField(
            model_name='voucher',
            name='voucher_type',
            field=models.CharField(choices=[('general', 'General Voucher'), ('dedicated', 'User-Specific Voucher')], default='general', max_length=10),
        ),
    ]
