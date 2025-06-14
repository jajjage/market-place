# Generated by Django 5.1.7 on 2025-06-08 22:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("categories", "0001_initial"),
        ("product_base", "0004_initial"),
        ("product_detail", "0004_alter_productdetail_unique_together_and_more"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="productdetail",
            new_name="product_pro_product_87df0d_idx",
            old_name="product_det_product_70d87a_idx",
        ),
        migrations.RenameIndex(
            model_name="productdetail",
            new_name="product_pro_product_d5fec3_idx",
            old_name="product_det_product_aa488c_idx",
        ),
        migrations.RenameIndex(
            model_name="productdetail",
            new_name="product_pro_product_79414b_idx",
            old_name="product_det_product_310c6c_idx",
        ),
        migrations.RenameIndex(
            model_name="productdetail",
            new_name="product_pro_detail__2ce083_idx",
            old_name="product_det_detail__54abc0_idx",
        ),
        migrations.RenameIndex(
            model_name="productdetail",
            new_name="product_pro_product_466467_idx",
            old_name="product_det_product_ef779a_idx",
        ),
        migrations.RenameIndex(
            model_name="productdetail",
            new_name="product_pro_templat_7233f6_idx",
            old_name="product_det_templat_abaad7_idx",
        ),
        migrations.AddField(
            model_name="productdetail",
            name="created_from_template",
            field=models.BooleanField(
                default=False,
                help_text="Whether this detail was created from a template",
            ),
        ),
        migrations.AddField(
            model_name="productdetail",
            name="template_version",
            field=models.PositiveIntegerField(
                default=1, help_text="Version of template when this detail was created"
            ),
        ),
        migrations.AddField(
            model_name="productdetailtemplate",
            name="applies_to_subcategories",
            field=models.BooleanField(
                default=True,
                help_text="Whether this template applies to subcategories as well",
            ),
        ),
        migrations.AddField(
            model_name="productdetailtemplate",
            name="description",
            field=models.TextField(
                blank=True, help_text="Template description for admins"
            ),
        ),
        migrations.AddField(
            model_name="productdetailtemplate",
            name="is_active",
            field=models.BooleanField(
                default=True, help_text="Whether this template is available for use"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="productdetail",
            unique_together={("product", "label", "detail_type")},
        ),
        migrations.AlterUniqueTogether(
            name="productdetailtemplate",
            unique_together={("label", "category", "detail_type")},
        ),
        migrations.AddIndex(
            model_name="productdetail",
            index=models.Index(
                fields=["created_from_template"], name="product_pro_created_6d323c_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="productdetailtemplate",
            index=models.Index(
                fields=["is_active"], name="product_det_is_acti_402b9f_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="productdetailtemplate",
            index=models.Index(
                fields=["category", "is_active"], name="product_det_categor_b0b102_idx"
            ),
        ),
        migrations.AlterModelTable(
            name="productdetail",
            table="product_product_details",
        ),
    ]
