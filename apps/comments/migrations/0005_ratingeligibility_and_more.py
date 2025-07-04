# Generated by Django 5.1.7 on 2025-07-02 23:17

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("comments", "0004_alter_userrating_options_and_more"),
        ("transactions", "0009_escrowtransaction_selected_options"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RatingEligibility",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("can_rate_from", models.DateTimeField()),
                ("rating_deadline", models.DateTimeField()),
                ("reminder_sent", models.BooleanField(default=False)),
                ("final_reminder_sent", models.BooleanField(default=False)),
            ],
            options={
                "db_table": "rating_eligibility",
            },
        ),
        migrations.RenameField(
            model_name="userrating",
            old_name="can_rate_from",
            new_name="moderated_at",
        ),
        migrations.RemoveField(
            model_name="userrating",
            name="rating_deadline",
        ),
        migrations.AddField(
            model_name="userrating",
            name="is_anonymous",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="userrating",
            name="is_flagged",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="userrating",
            name="moderated_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="moderated_ratings",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="userrating",
            name="moderation_notes",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="userrating",
            name="comment",
            field=models.TextField(blank=True, max_length=1000),
        ),
        migrations.AddIndex(
            model_name="userrating",
            index=models.Index(
                fields=["to_user", "-created_at"], name="user_rating_to_user_edb929_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="userrating",
            index=models.Index(
                fields=["from_user", "-created_at"],
                name="user_rating_from_us_6d0c6b_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="userrating",
            index=models.Index(
                fields=["rating", "-created_at"], name="user_rating_rating_03e62c_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="userrating",
            index=models.Index(
                fields=["is_flagged"], name="user_rating_is_flag_1df40c_idx"
            ),
        ),
        migrations.AddField(
            model_name="ratingeligibility",
            name="transaction",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="rating_eligibility",
                to="transactions.escrowtransaction",
            ),
        ),
        migrations.AddIndex(
            model_name="ratingeligibility",
            index=models.Index(
                fields=["rating_deadline"], name="rating_elig_rating__306710_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="ratingeligibility",
            index=models.Index(
                fields=["can_rate_from"], name="rating_elig_can_rat_8532d7_idx"
            ),
        ),
    ]
