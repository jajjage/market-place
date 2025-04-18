# Generated by Django 5.1.7 on 2025-04-08 23:15

import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomUser",
            fields=[
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
                    "date_joined",
                    models.DateTimeField(
                        default=django.utils.timezone.now, verbose_name="date joined"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        max_length=254, unique=True, verbose_name="email address"
                    ),
                ),
                ("first_name", models.CharField(blank=True, max_length=150)),
                ("last_name", models.CharField(blank=True, max_length=150)),
                (
                    "user_type",
                    models.CharField(
                        choices=[
                            ("BUYER", "Buyer"),
                            ("SELLER", "Seller"),
                            ("ADMIN", "Admin"),
                        ],
                        default="BUYER",
                        max_length=10,
                    ),
                ),
                (
                    "verification_status",
                    models.CharField(
                        choices=[
                            ("UNVERIFIED", "Unverified"),
                            ("PENDING", "Pending"),
                            ("VERIFIED", "Verified"),
                        ],
                        default="UNVERIFIED",
                        max_length=10,
                    ),
                ),
                ("is_active", models.BooleanField(default=False)),
                ("is_staff", models.BooleanField(default=False)),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.group",
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
                        to="auth.permission",
                        verbose_name="user permissions",
                    ),
                ),
            ],
            options={
                "db_table": "core_user",
            },
        ),
        migrations.CreateModel(
            name="UserProfile",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("bio", models.TextField(blank=True)),
                ("address", models.JSONField(blank=True, default=dict)),
                ("profile_picture", models.CharField(blank=True, max_length=255)),
                ("phone_number", models.CharField(blank=True, max_length=20)),
                (
                    "id_verification_documents",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "rating",
                    models.DecimalField(decimal_places=2, default=0.0, max_digits=3),
                ),
                ("total_reviews", models.IntegerField(default=0)),
                ("is_featured", models.BooleanField(default=False)),
                ("social_links", models.JSONField(blank=True, default=dict)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.AddIndex(
            model_name="customuser",
            index=models.Index(
                fields=["email", "is_active"], name="core_user_email_c0c03f_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="customuser",
            index=models.Index(
                fields=["first_name", "last_name"], name="core_user_first_n_7ed624_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="customuser",
            constraint=models.CheckConstraint(
                condition=models.Q(("email__isnull", False)),
                name="staff_email_not_null",
            ),
        ),
    ]
