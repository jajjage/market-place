# Generated by Django 5.1.7 on 2025-06-07 10:54

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("categories", "0001_initial"),
        ("product_base", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductDetailTemplate",
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
                (
                    "detail_type",
                    models.CharField(
                        choices=[
                            ("specification", "Specification"),
                            ("feature", "Feature"),
                            ("description", "Description"),
                            ("warning", "Warning"),
                            ("care_instruction", "Care Instruction"),
                            ("dimension", "Dimension"),
                            ("material", "Material"),
                            ("compatibility", "Compatibility"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=20,
                    ),
                ),
                ("label", models.CharField(max_length=100)),
                ("unit", models.CharField(blank=True, max_length=20)),
                ("is_required", models.BooleanField(default=False)),
                ("placeholder_text", models.TextField(blank=True)),
                ("validation_regex", models.CharField(blank=True, max_length=200)),
                ("display_order", models.PositiveIntegerField(default=0)),
                (
                    "category",
                    models.ForeignKey(
                        blank=True,
                        help_text="Category-specific template",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="categories.category",
                    ),
                ),
            ],
            options={
                "db_table": "product_detail_templates",
                "ordering": ["display_order", "label"],
            },
        ),
        migrations.CreateModel(
            name="ProductDetail",
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
                (
                    "detail_type",
                    models.CharField(
                        choices=[
                            ("specification", "Specification"),
                            ("feature", "Feature"),
                            ("description", "Description"),
                            ("warning", "Warning"),
                            ("care_instruction", "Care Instruction"),
                            ("dimension", "Dimension"),
                            ("material", "Material"),
                            ("compatibility", "Compatibility"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=20,
                    ),
                ),
                ("label", models.CharField(max_length=100)),
                ("value", models.TextField()),
                ("unit", models.CharField(blank=True, max_length=20)),
                ("is_highlighted", models.BooleanField(default=False)),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="product_details",
                        to="product_base.product",
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="product_details",
                        to="product_detail.productdetailtemplate",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Product Details",
                "db_table": "product_product_details",
                "ordering": ["display_order", "label"],
            },
        ),
        migrations.AddIndex(
            model_name="productdetailtemplate",
            index=models.Index(
                fields=["detail_type"], name="product_det_detail__48afe0_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="productdetailtemplate",
            index=models.Index(
                fields=["category", "detail_type"],
                name="product_det_categor_8bd62b_idx",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="productdetailtemplate",
            unique_together={("label", "category", "detail_type")},
        ),
        migrations.AddIndex(
            model_name="productdetail",
            index=models.Index(
                fields=["product", "detail_type"], name="product_pro_product_87df0d_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="productdetail",
            index=models.Index(
                fields=["product", "is_highlighted"],
                name="product_pro_product_d5fec3_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="productdetail",
            index=models.Index(
                fields=["product", "display_order"],
                name="product_pro_product_79414b_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="productdetail",
            index=models.Index(
                fields=["detail_type", "is_highlighted"],
                name="product_pro_detail__2ce083_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="productdetail",
            index=models.Index(
                fields=["product", "is_active"], name="product_pro_product_466467_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="productdetail",
            index=models.Index(
                fields=["template"], name="product_pro_templat_7233f6_idx"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="productdetail",
            unique_together={("product", "label", "detail_type")},
        ),
    ]
