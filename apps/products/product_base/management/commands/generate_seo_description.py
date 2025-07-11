# your_app_name/management/commands/generate_seo_description.py


import uuid
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.products.product_base.tasks import generate_seo_description_for_product

# from apps.products.product_base.utils.description_utils import (
#     generate_fallback_description,
# )


class Command(BaseCommand):
    """
    Django management command to generate an SEO description for a product.
    """

    help = "Generates an SEO-optimized product description using Google GenAI for a given product ID."

    def add_arguments(self, parser):
        """
        Define the command-line arguments.
        """
        parser.add_argument(
            "product_id",
            type=uuid.UUID,
            help="The ID of the product to generate a description for.",
        )
        parser.add_argument(
            "--type",
            type=str,
            default="detailed",
            help="The type of description to generate (e.g., short, detailed, marketing).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force regeneration even if a description already exists.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        """
        The main logic of the command.
        """
        product_id = options["product_id"]
        description_type = options["type"]
        force_regeneration = options["force"]

        try:
            generate_seo_description_for_product(product_id, description_type)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully generated and saved new description for product ID {product_id}."
                )
            )
            # description = generate_fallback_description(product_id)
        except Exception as e:
            raise CommandError(f"An unexpected error occurred: {e}")
