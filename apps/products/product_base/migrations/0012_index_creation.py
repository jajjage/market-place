# Generated migration file for Django
from django.db import migrations


class Migration(migrations.Migration):
    atomic = False  # Required for CREATE INDEX CONCURRENTLY

    dependencies = [
        (
            "product_base",
            "0011_alter_product_price",
        ),  # Replace with your latest migration
    ]

    operations = [
        # Primary lookup index for product short codes
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_short_code ON product(short_code);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_short_code;",
        ),
        # Variant-related indexes
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_variant_product_id ON product_variant(product_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_variant_product_id;",
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_variant_option_variant_type_id ON product_variant_option(variant_type_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_variant_option_variant_type_id;",
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_variant_options_variant_id ON product_variant_options(productvariant_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_variant_options_variant_id;",
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_variant_image_variant_id ON product_variant_image(variant_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_variant_image_variant_id;",
        ),
        # Product details indexes
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_detail_product_id_active ON product_product_details(product_id, is_active);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_detail_product_id_active;",
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_detail_display_order ON product_product_details(display_order, label);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_detail_display_order;",
        ),
        # Product images indexes
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_image_product_id_active_primary ON product_product_images(product_id, is_active, is_primary);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_image_product_id_active_primary;",
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_image_display_order ON product_product_images(display_order);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_image_display_order;",
        ),
        # Ratings indexes
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_rating_product_id_approved ON product_rating(product_id, is_approved);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_rating_product_id_approved;",
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_rating_created_at ON product_rating(created_at DESC);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_rating_created_at;",
        ),
        # Watchlist indexes
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_watchlist_product_id ON product_watchlist(product_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_watchlist_product_id;",
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_watchlist_user_product ON product_watchlist(user_id, product_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_watchlist_user_product;",
        ),
        # Additional optimization indexes
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_variant_option_sort ON product_variant_option(sort_order, value);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_variant_option_sort;",
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_escrow_transaction_product_seller ON escrow_transactions(product_id, seller_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_escrow_transaction_product_seller;",
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_metadata_product_id ON product_metadata(product_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_metadata_product_id;",
        ),
    ]
