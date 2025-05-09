# Generated by Django 5.1.7 on 2025-05-07 17:08

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("products", "0001_initial"),
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
            model_name="product",
            name="category",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, to="products.category"
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="seller",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="products",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="inventorytransaction",
            name="product",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="inventory_transactions",
                to="products.product",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="condition",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to="products.productcondition",
            ),
        ),
        migrations.AddField(
            model_name="productimage",
            name="product",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="images",
                to="products.product",
            ),
        ),
        migrations.AddField(
            model_name="productmeta",
            name="product",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="meta",
                to="products.product",
            ),
        ),
        migrations.AddField(
            model_name="productwatchlistitem",
            name="product",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="watchers",
                to="products.product",
            ),
        ),
        migrations.AddField(
            model_name="productwatchlistitem",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="watchlist",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(fields=["slug"], name="products_slug_5e91f2_idx"),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(
                fields=["short_code"], name="products_short_c_9d2269_idx"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="product",
            unique_together={("slug", "short_code")},
        ),
        migrations.AlterUniqueTogether(
            name="productwatchlistitem",
            unique_together={("user", "product")},
        ),
    ]
