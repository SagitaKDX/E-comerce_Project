# Generated by Django 5.1.6 on 2025-04-03 05:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0009_notification'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='title',
            field=models.CharField(default='Notification', max_length=100),
        ),
    ]
