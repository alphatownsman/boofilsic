# Generated by Django 4.2.4 on 2023-08-10 18:55

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        (
            "journal",
            "0013_remove_comment_focus_item",
        ),
    ]

    operations = [
        migrations.RemoveField(
            model_name="reply",
            name="piece_ptr",
        ),
        migrations.RemoveField(
            model_name="reply",
            name="reply_to_content",
        ),
        migrations.DeleteModel(
            name="Memo",
        ),
        migrations.DeleteModel(
            name="Reply",
        ),
    ]
