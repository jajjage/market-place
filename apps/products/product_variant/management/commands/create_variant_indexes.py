from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Creates concurrent indexes for product variant optimization"

    def handle(self, *args, **kwargs):
        with connection.cursor() as cursor:
            # Set autocommit mode which is required for concurrent index creation
            old_autocommit = connection.autocommit
            connection.autocommit = True

            try:
                # Create indexes one by one
                self.stdout.write("Creating variant type lookup index...")
                cursor.execute(
                    """
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_variant_type_lookup 
                    ON product_variant_type(id, name, is_active);
                """
                )

                self.stdout.write("Creating variant options lookup index...")
                cursor.execute(
                    """
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_variant_options_lookup 
                    ON product_variant_option(variant_type_id, sort_order, value);
                """
                )

                self.stdout.write("Creating product variant lookup index...")
                cursor.execute(
                    """
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_variant_lookup 
                    ON product_variant(product_id, id);
                """
                )

                self.stdout.write("Creating variant image lookup index...")
                cursor.execute(
                    """
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_variant_image_lookup 
                    ON product_variant_image(variant_id, sort_order);
                """
                )

                self.stdout.write(
                    self.style.SUCCESS("Successfully created all concurrent indexes")
                )

            finally:
                connection.autocommit = old_autocommit
