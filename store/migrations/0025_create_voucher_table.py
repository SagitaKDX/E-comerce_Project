# Generated manually to fix database issues

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0024_remove_cart_voucher_remove_order_notes_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Voucher',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=20, unique=True)),
                ('discount_type', models.CharField(choices=[('percentage', 'Percentage'), ('fixed', 'Fixed Amount')], default='percentage', max_length=10)),
                ('discount_value', models.DecimalField(decimal_places=2, max_digits=10)),
                ('max_discount', models.DecimalField(blank=True, decimal_places=2, help_text='Maximum discount amount for percentage discounts', max_digits=10, null=True)),
                ('valid_from', models.DateTimeField(default=django.utils.timezone.now)),
                ('valid_to', models.DateTimeField(default=django.utils.timezone.now)),
                ('is_active', models.BooleanField(default=True)),
                ('min_purchase_amount', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('usage_limit', models.PositiveIntegerField(default=1, help_text='Number of times this voucher can be used')),
                ('used_count', models.PositiveIntegerField(default=0, help_text='Number of times this voucher has been used')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-valid_from'],
            },
        ),
    ] 