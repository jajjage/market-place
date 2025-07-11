from django.core.management.base import BaseCommand

# from django.db import transaction
from apps.products.product_base.models import Product
from apps.products.product_search.documents import ProductDocument


class Command(BaseCommand):
    help = "Update Elasticsearch index for products with metadata"

    def add_arguments(self, parser):
        parser.add_argument(
            "--rebuild",
            action="store_true",
            help="Rebuild the entire index",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Batch size for indexing",
        )

    def handle(self, *args, **options):
        if options["rebuild"]:
            self.stdout.write("Rebuilding product search index...")

            # Delete existing index
            try:
                ProductDocument._index.delete()
                self.stdout.write("Deleted existing index")
            except:
                pass

            # Create new index
            ProductDocument._index.create()
            self.stdout.write("Created new index")

        # Get all active products with metadata
        products = Product.objects.select_related(
            "seller", "category", "brand", "condition", "meta"
        ).prefetch_related("ratings")

        batch_size = options["batch_size"]
        total_products = products.count()

        self.stdout.write(f"Indexing {total_products} products...")

        for i in range(0, total_products, batch_size):
            batch = products[i : i + batch_size]

            # Index batch
            documents = []
            for product in batch:
                doc = ProductDocument()
                doc.meta.id = product.id
                doc.update(product)
                documents.append(doc)

            # Bulk index
            from elasticsearch.helpers import bulk

            # Prepare actions for bulk helper
            actions = [doc.to_dict(include_meta=True) for doc in documents]
            bulk(
                ProductDocument._get_connection(),
                actions,
                index=ProductDocument._index._name,
            )

            self.stdout.write(
                f"Indexed {min(i + batch_size, total_products)}/{total_products} products"
            )

        self.stdout.write(
            self.style.SUCCESS(f"Successfully indexed {total_products} products")
        )
