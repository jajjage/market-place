# Generated by Django 5.1.7 on 2025-06-24 05:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("product_base", "0008_alter_product_slug"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="product",
            name="available_inventory",
        ),
        migrations.RemoveField(
            model_name="product",
            name="in_escrow_inventory",
        ),
        migrations.RemoveField(
            model_name="product",
            name="total_inventory",
        ),
        migrations.AddField(
            model_name="product",
            name="require_inspection",
            field=models.BooleanField(default=False),
        ),
    ]
