# Generated by Django 5.0.3 on 2024-05-24 15:17

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("base_app", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="csrf_token",
            field=models.CharField(default="", max_length=100),
        ),
    ]
