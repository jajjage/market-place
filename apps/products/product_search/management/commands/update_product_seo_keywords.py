import logging
from django.db import transaction
from django.core.management.base import BaseCommand
from django.db.models import Q
from apps.products.product_base.models import Product
from apps.products.product_metadata.models import ProductMeta
from apps.products.product_metadata.utils.keywords_context import (
    extract_product_keywords_and_context,
    generate_fallback_keywords,
)
from apps.products.product_metadata.utils.seo_generate import (
    GoogleGenAISEOKeywordService,
)


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Generate SEO keywords for products that don't have them"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force update even if keywords already exist",
        )

    def handle(self, *args, **options):
        # Get products without SEO keywords or force update
        if options["force"]:
            products = Product.objects.filter(is_active=True)
        else:
            products = Product.objects.filter(
                Q(meta__seo_keywords="") | Q(meta__isnull=True), is_active=True
            )

        updated_count = 0

        for product in products.select_related("brand", "category", "condition"):
            keywords = self.generate_seo_keywords(product)
            logger.info(f"Generated keywords for product {product.id}: {keywords}")

            # Ensure keywords is a non-null string
            if not keywords:
                logger.warning(f"No keywords generated for product {product.id}")
                keywords = ""

            # Get or create metadata
            with transaction.atomic():
                meta, created = ProductMeta.objects.get_or_create(
                    product=product,
                    defaults={"seo_keywords": keywords, "seo_generation_queued": True},
                )

                if not created and (options["force"] or not meta.seo_keywords):
                    meta.seo_keywords = keywords
                    meta.seo_generation_queued = True
                    meta.save()

                updated_count += 1

                if updated_count % 100 == 0:
                    self.stdout.write(f"Updated {updated_count} products...")

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully updated SEO keywords for {updated_count} products"
            )
        )

    def generate_seo_keywords(self, product):
        """Generate SEO keywords based on product attributes"""
        # Get the product

        # Extract product information to build seed term and context
        seed_term, context_info = extract_product_keywords_and_context(product)

        if not seed_term:
            logger.warning(f"No seed term could be generated for product {product.id}")
            seed_term = "product"  # Fallback

        # Initialize the GenAI service
        try:
            service = GoogleGenAISEOKeywordService()

            # Generate keywords using AI with product context
            keywords = service.generate_keywords(
                seed_term=seed_term,
                count=25,  # Generate more keywords for better selection
                intent_filter="commercial",  # Focus on commercial intent for products
                target_audience=context_info.get("target_audience"),
                business_type="e-commerce",
            )

            # If AI generation fails, use fallback method
            if not keywords:
                logger.warning(
                    f"AI keyword generation failed for product {product.id}, using fallback"
                )
                keywords = generate_fallback_keywords(product, seed_term)
            return keywords
        except Exception as e:
            logger.error(
                f"Error with GoogleGenAISEOKeywordService for product {product.id}: {str(e)}"
            )
            keywords = generate_fallback_keywords(product, seed_term)
