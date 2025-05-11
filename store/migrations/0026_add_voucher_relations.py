# Generated manually to fix database issues

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0025_create_voucher_table'),
    ]

    operations = [
        migrations.AddField(
            model_name='cart',
            name='active_voucher',
            field=models.ForeignKey('Voucher', related_name='carts', on_delete=django.db.models.deletion.SET_NULL, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='order',
            name='voucher',
            field=models.ForeignKey('Voucher', on_delete=django.db.models.deletion.SET_NULL, null=True, blank=True),
        ),
    ] 