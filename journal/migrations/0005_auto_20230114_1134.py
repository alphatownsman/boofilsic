# Generated by Django 3.2.16 on 2023-01-14 03:34

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("journal", "0004_alter_shelflogentry_timestamp"),
    ]

    operations = [
        migrations.CreateModel(
            name="FeaturedCollection",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_time", models.DateTimeField(auto_now_add=True)),
                ("edited_time", models.DateTimeField(auto_now=True)),
                (
                    "collection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="journal.collection",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "unique_together": {("owner", "collection")},
            },
        ),
        migrations.AddField(
            model_name="collection",
            name="featured_by_users",
            field=models.ManyToManyField(
                related_name="featured_collections",
                through="journal.FeaturedCollection",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
