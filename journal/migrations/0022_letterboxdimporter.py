# Generated by Django 4.2.9 on 2024-01-11 01:47

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0019_task"),
        ("journal", "0021_pieceinteraction_pieceinteraction_unique_interaction"),
    ]

    operations = [
        migrations.CreateModel(
            name="LetterboxdImporter",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("users.task",),
        ),
    ]
