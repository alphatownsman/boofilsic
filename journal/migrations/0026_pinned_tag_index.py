# Generated by Django 4.2.13 on 2024-06-05 00:45

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("journal", "0025_pin_tags"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="tag",
            index=models.Index(
                fields=["owner", "pinned"], name="journal_tag_owner_i_068598_idx"
            ),
        ),
    ]
