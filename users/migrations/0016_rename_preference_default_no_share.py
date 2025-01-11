# Generated by Django 4.2.8 on 2023-12-10 19:26

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0015_remove_preference_mastodon_publish_public_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="preference",
            name="mastodon_default_repost",
            field=models.BooleanField(default=True),
        ),
        migrations.RunSQL(
            "UPDATE users_preference SET mastodon_default_repost = false where default_no_share = true;"
        ),
        migrations.RemoveField(
            model_name="preference",
            name="default_no_share",
        ),
    ]
