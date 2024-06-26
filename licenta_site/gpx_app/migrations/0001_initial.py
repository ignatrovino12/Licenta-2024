# Generated by Django 5.0.3 on 2024-05-24 15:17

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("base_app", "0002_alter_userprofile_csrf_token"),
    ]

    operations = [
        migrations.CreateModel(
            name="Video",
            fields=[
                ("video_id", models.AutoField(primary_key=True, serialize=False)),
                ("video_name", models.CharField(max_length=100)),
                (
                    "user_profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="base_app.userprofile",
                    ),
                ),
            ],
        ),
    ]
