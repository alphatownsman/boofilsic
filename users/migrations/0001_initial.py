# Generated by Django 3.2.16 on 2023-01-12 01:32

import django.contrib.auth.models
import django.core.serializers.json
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="User",
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
                ("password", models.CharField(max_length=128, verbose_name="password")),
                (
                    "last_login",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="last login"
                    ),
                ),
                (
                    "is_superuser",
                    models.BooleanField(
                        default=False,
                        help_text="Designates that this user has all permissions without explicitly assigning them.",
                        verbose_name="superuser status",
                    ),
                ),
                (
                    "first_name",
                    models.CharField(
                        blank=True, max_length=150, verbose_name="first name"
                    ),
                ),
                (
                    "last_name",
                    models.CharField(
                        blank=True, max_length=150, verbose_name="last name"
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        blank=True, max_length=254, verbose_name="email address"
                    ),
                ),
                (
                    "is_staff",
                    models.BooleanField(
                        default=False,
                        help_text="Designates whether the user can log into this admin site.",
                        verbose_name="staff status",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Designates whether this user should be treated as active. Unselect this instead of deleting accounts.",
                        verbose_name="active",
                    ),
                ),
                (
                    "date_joined",
                    models.DateTimeField(
                        default=django.utils.timezone.now, verbose_name="date joined"
                    ),
                ),
                (
                    "username",
                    models.CharField(
                        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
                        max_length=150,
                        verbose_name="username",
                    ),
                ),
                ("following", models.JSONField(default=list)),
                ("mastodon_id", models.CharField(max_length=100)),
                ("mastodon_site", models.CharField(max_length=100)),
                ("mastodon_token", models.CharField(default="", max_length=2048)),
                (
                    "mastodon_refresh_token",
                    models.CharField(default="", max_length=2048),
                ),
                ("mastodon_locked", models.BooleanField(default=False)),
                ("mastodon_followers", models.JSONField(default=list)),
                ("mastodon_following", models.JSONField(default=list)),
                ("mastodon_mutes", models.JSONField(default=list)),
                ("mastodon_blocks", models.JSONField(default=list)),
                ("mastodon_domain_blocks", models.JSONField(default=list)),
                ("mastodon_account", models.JSONField(default=dict)),
                (
                    "mastodon_last_refresh",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                ("read_announcement_index", models.PositiveIntegerField(default=0)),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.Group",
                        verbose_name="groups",
                    ),
                ),
                (
                    "user_permissions",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Specific permissions for this user.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.Permission",
                        verbose_name="user permissions",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Preference",
            fields=[
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        serialize=False,
                        to="users.user",
                    ),
                ),
                ("profile_layout", models.JSONField(blank=True, default=list)),
                (
                    "export_status",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        encoder=django.core.serializers.json.DjangoJSONEncoder,
                        null=True,
                    ),
                ),
                (
                    "import_status",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        encoder=django.core.serializers.json.DjangoJSONEncoder,
                        null=True,
                    ),
                ),
                ("default_visibility", models.PositiveSmallIntegerField(default=0)),
                ("classic_homepage", models.BooleanField(default=False)),
                ("mastodon_publish_public", models.BooleanField(default=False)),
                ("mastodon_append_tag", models.CharField(default="", max_length=2048)),
                ("show_last_edit", models.PositiveSmallIntegerField(default=0)),
                ("no_anonymous_view", models.PositiveSmallIntegerField(default=0)),
            ],
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                fields=("username", "mastodon_site"), name="unique_user_identity"
            ),
        ),
    ]
