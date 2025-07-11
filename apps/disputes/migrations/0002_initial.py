# Generated by Django 5.1.7 on 2025-06-07 10:54

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("disputes", "0001_initial"),
        ("transactions", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="dispute",
            name="opened_by",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="opened_disputes",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="dispute",
            name="transaction",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="dispute",
                to="transactions.escrowtransaction",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="dispute",
            unique_together={("transaction", "opened_by")},
        ),
    ]
