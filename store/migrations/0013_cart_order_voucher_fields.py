# Generated manually to fix migration issues

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0012_voucher'),
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
        migrations.AddField(
            model_name='order',
            name='voucher_discount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='order',
            name='phone_number',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='subtotal',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='order',
            name='total_price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ] 