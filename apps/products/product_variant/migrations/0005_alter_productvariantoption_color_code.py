# Generated by Django 5.1.7 on 2025-07-18 14:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("product_variant", "0004_remove_productvariant_escrow_hold_period_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="productvariantoption",
            name="color_code",
            field=models.CharField(
                blank=True,
                help_text="Hex color code for color swatches",
                max_length=7,
                null=True,
            ),
        ),
    ]
