# Generated by Django 5.1.7 on 2025-06-07 10:54

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("product_base", "0004_initial"),
        ("product_inventory", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="inventorytransaction",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="inventorytransaction",
            name="product",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="inventory_transactions",
                to="product_base.product",
            ),
        ),
        migrations.AddIndex(
            model_name="inventorytransaction",
            index=models.Index(
                fields=["transaction_type"], name="product_inv_transac_afb739_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="inventorytransaction",
            index=models.Index(
                fields=["product", "-created_at"], name="product_inv_product_e7020f_idx"
            ),
        ),
    ]
