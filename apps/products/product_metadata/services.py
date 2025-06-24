from datetime import timezone
import logging
from django.db import transaction, models
from django.db.models import Case, When
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

from apps.core.utils.cache_manager import CacheManager
from apps.products.product_base.models import Product
from .tasks import generate_seo_keywords_for_product
from .models import ProductMeta
from apps.core.utils.cache_key_manager import CacheKeyManager


logger = logging.getLogger(__name__)


class ProductMetaService:

    @staticmethod
    @transaction.atomic
    def increment_product_view_count(product_id: int, use_cache_buffer: bool = True):
        logger.info(
            "→ increment_product_view_count START (product_id=%s, use_cache_buffer=%s)",
            product_id,
            use_cache_buffer,
        )

        # 1) Existence check
        try:
            exists = Product.objects.filter(pk=product_id, is_active=True).exists()
        except Exception:
            logger.exception("Failed during existence check for Product %s", product_id)
            raise
        if not exists:
            logger.error("Product %s does not exist or is inactive", product_id)
            raise ValueError(
                f"Product with ID {product_id} does not exist or is inactive"
            )

        # 2) get_or_create ProductMeta
        try:
            product_meta, created = ProductMeta.objects.get_or_create(
                product_id=product_id,
                defaults={"views_count": 0, "seo_keywords": ""},
            )
            logger.info("ProductMeta %s — created=%s", product_meta.pk, created)
        except Exception:
            logger.exception("Failed to get_or_create ProductMeta for %s", product_id)
            raise

        with transaction.atomic():
            print("inside the meta")
            pm_locked = ProductMeta.objects.select_for_update().get(
                product_id=product_id
            )

            # only queue if neither keywords nor a queued flag exist
            logger.info(
                f"{not pm_locked.seo_keywords} : {not pm_locked.seo_generation_queued}"
            )
            if not pm_locked.seo_keywords and not pm_locked.seo_generation_queued:
                logger.info(f"Queueing SEO generation for product {product_id}")
                transaction.on_commit(
                    lambda: generate_seo_keywords_for_product.delay(product_id)
                )

        if use_cache_buffer:
            # 3) Build cache key
            try:
                cache_key = CacheKeyManager.make_key(
                    "product_meta",
                    "views_buffer",
                    id=str(product_id),  # ensure the ID goes into the key!
                )
                logger.debug("Cache key = %s", cache_key)
            except Exception:
                logger.exception("Failed to build cache_key for %s", product_id)
                raise

            # 4) Increment or initialize buffer
            try:
                buffer_val = cache.incr(cache_key, delta=1)
                logger.debug("cache.incr returned %s", buffer_val)
            except ValueError as e:
                logger.warning("cache.incr failed (%s), setting to 1", e)
                cache.set(cache_key, 1, timeout=None)
                buffer_val = 1

            # 5) Maybe flush to DB
            FLUSH_THRESHOLD = 10
            if buffer_val >= FLUSH_THRESHOLD:
                logger.info("Buffer %s ≥ threshold, flushing to DB", buffer_val)
                try:
                    with transaction.atomic():
                        pm_locked = ProductMeta.objects.select_for_update().get(
                            product_id=product_id
                        )
                        pm_locked.views_count = models.F("views_count") + buffer_val
                        pm_locked.save(update_fields=["views_count", "updated_at"])
                        cache.set(cache_key, 0, timeout=None)
                        logger.info("Flushed %s views into DB", buffer_val)
                        CacheManager.invalidate_key(
                            "product_base",
                            "detail_by_shortcode",
                            short_code=pm_locked.product.short_code,
                        )
                        logger.info(f"the short code : {pm_locked.product.short_code}")
                except Exception:
                    logger.exception(
                        "Error flushing view buffer to DB for %s", product_id
                    )
                    raise

            logger.info(
                "→ increment_product_view_count END (buffered) for %s", product_id
            )
            return product_meta

        # 6) Direct DB update path
        try:
            ProductMeta.objects.filter(product_id=product_id).update(
                views_count=models.F("views_count") + 1,
                updated_at=timezone.now(),
            )
            pm = ProductMeta.objects.get(product_id=product_id)
            logger.info(
                "→ increment_product_view_count END (direct) new count=%s",
                pm.views_count,
            )
            return pm
        except Exception:
            logger.exception("Failed direct update of views_count for %s", product_id)
            raise

    @staticmethod
    @transaction.atomic
    def get_or_create_product_meta(product_id: int, user, data: dict):
        """
        Update ProductMeta for a product owned by the user.
        This enforces ownership rules for metadata management.
        """
        from apps.products.product_base.models import Product

        product = get_object_or_404(Product, pk=product_id, is_active=True)

        # Check ownership
        if hasattr(product, "owner") and product.owner != user:
            raise PermissionDenied("You can only update metadata for your own products")

        # Get or create the metadata
        product_meta, created = ProductMeta.objects.get_or_create(
            product=product,
            defaults={
                "views_count": 0,
                "seo_keywords": "",
            },
        )

        # Update with provided data
        for field, value in data.items():
            if hasattr(product_meta, field):
                # Special handling for seo_keywords validation
                if field == "seo_keywords":
                    value = ProductMetaService.validate_seo_keywords_format(value)
                setattr(product_meta, field, value)

        product_meta.save()
        return product_meta, created

    @staticmethod
    def get_product_meta_by_product(product_id: int = None, product_slug: str = None):
        """
        Get ProductMeta by product ID or slug. Creates if doesn't exist.
        This is for public access (like getting SEO data for a product page).
        """
        from apps.products.product_base.models import Product

        if not product_id and not product_slug:
            raise ValueError("Either product_id or product_slug is required")

        # Build lookup
        lookup = {"pk": product_id} if product_id else {"slug": product_slug}
        product = get_object_or_404(Product, is_active=True, **lookup)

        # Get or create metadata
        product_meta, created = ProductMeta.objects.get_or_create(
            product=product,
            defaults={
                "views_count": 0,
                "meta_title": product.name,
                "meta_description": (
                    getattr(product, "description", "")[:160]
                    if hasattr(product, "description")
                    else ""
                ),
                "seo_keywords": "",
            },
        )

        return product_meta

    @staticmethod
    def get_featured_products_meta(limit: int = 10):
        """
        Return a queryset of ProductMeta for featured products, ordered by views.
        Caches the list of IDs for performance.
        """
        from apps.products.product_base.models import Product

        # Get featured product IDs
        featured_product_ids = Product.objects.filter(
            is_featured=True, is_active=True
        ).values_list("id", flat=True)

        cache_key = CacheKeyManager.make_key(
            "product_meta", "featured_ids", limit=limit
        )
        meta_ids = cache.get(cache_key)

        if meta_ids is None:
            # Get existing ProductMeta for featured products
            existing_meta = (
                ProductMeta.objects.filter(product_id__in=featured_product_ids)
                .order_by("-views_count")
                .values_list("pk", "product_id")[:limit]
            )

            existing_meta_dict = dict(existing_meta)
            meta_ids = list(existing_meta_dict.keys())

            # Create missing ProductMeta for featured products that don't have them
            existing_product_ids = set(existing_meta_dict.values())
            missing_product_ids = set(featured_product_ids) - existing_product_ids

            if missing_product_ids:
                # Create missing metadata entries
                missing_products = Product.objects.filter(id__in=missing_product_ids)
                missing_meta_objs = []

                for product in missing_products:
                    missing_meta_objs.append(
                        ProductMeta(
                            product=product,
                            views_count=0,
                            meta_title=product.name,
                            meta_description=(
                                getattr(product, "description", "")[:160]
                                if hasattr(product, "description")
                                else ""
                            ),
                            seo_keywords="",
                        )
                    )

                if missing_meta_objs:
                    ProductMeta.objects.bulk_create(
                        missing_meta_objs, ignore_conflicts=True
                    )
                    # Refresh the query to include new entries
                    meta_ids = list(
                        ProductMeta.objects.filter(product_id__in=featured_product_ids)
                        .order_by("-views_count")
                        .values_list("pk", flat=True)[:limit]
                    )

            cache.set(cache_key, meta_ids, timeout=300)  # Cache for 5 minutes

        # Return ordered queryset
        if meta_ids:
            preserved_order = Case(
                *[When(pk=pk, then=pos) for pos, pk in enumerate(meta_ids)]
            )
            return ProductMeta.objects.filter(pk__in=meta_ids).order_by(preserved_order)

        return ProductMeta.objects.none()

    @staticmethod
    def get_popular_products_meta(limit: int = 10):
        """
        Return a queryset of most popular ProductMeta based on view count.
        Only includes metadata for active products.
        """
        return (
            ProductMeta.objects.select_related("product")
            .filter(product__is_active=True)
            .order_by("-views_count")[:limit]
        )

    @staticmethod
    def get_user_products_meta(user, limit: int = None):
        """
        Get ProductMeta for all products owned by a user.
        Creates metadata if it doesn't exist for any of their products.
        """
        from apps.products.product_base.models import Product

        # Get user's products
        user_products = Product.objects.filter(owner=user, is_active=True)

        if limit:
            user_products = user_products[:limit]

        # Get existing metadata
        existing_meta = ProductMeta.objects.filter(
            product__in=user_products
        ).select_related("product")

        existing_product_ids = set(existing_meta.values_list("product_id", flat=True))

        # Create missing metadata
        missing_products = user_products.exclude(id__in=existing_product_ids)

        if missing_products.exists():
            missing_meta_objs = []
            for product in missing_products:
                missing_meta_objs.append(
                    ProductMeta(
                        product=product,
                        views_count=0,
                        meta_title=product.name,
                        meta_description=(
                            getattr(product, "description", "")[:160]
                            if hasattr(product, "description")
                            else ""
                        ),
                        seo_keywords="",
                    )
                )

            if missing_meta_objs:
                ProductMeta.objects.bulk_create(
                    missing_meta_objs, ignore_conflicts=True
                )

        # Return all metadata for user's products
        return (
            ProductMeta.objects.filter(product__owner=user, product__is_active=True)
            .select_related("product")
            .order_by("-updated_at")
        )

    @staticmethod
    def validate_seo_keywords_format(raw_value: str) -> str:
        """
        Cleans and validates a comma-separated string of SEO keywords.
        Raises ValueError on invalid format.
        """
        if not raw_value:
            return ""

        cleaned = " ".join(raw_value.strip().split())
        keywords = [k.strip() for k in cleaned.split(",") if k.strip()]

        MAX_KEYWORD_LENGTH = 50
        for kw in keywords:
            if len(kw) > MAX_KEYWORD_LENGTH:
                raise ValueError(
                    f"Keyword '{kw[:20]}...' exceeds the max length of {MAX_KEYWORD_LENGTH} characters."
                )

        MAX_KEYWORDS = 10
        if len(keywords) > MAX_KEYWORDS:
            raise ValueError(f"Cannot have more than {MAX_KEYWORDS} keywords.")

        return ",".join(keywords)  # Return a consistently formatted string

    @staticmethod
    @transaction.atomic
    def bulk_create_missing_metadata():
        """
        Utility function to create ProductMeta for all products that don't have them.
        This can be run as a management command or migration.
        """
        from apps.products.product_base.models import Product

        # Find products without metadata
        products_without_meta = Product.objects.filter(
            is_active=True, productmeta__isnull=True
        )

        meta_objects = []
        for product in products_without_meta:
            meta_objects.append(
                ProductMeta(
                    product=product,
                    views_count=0,
                    meta_title=product.name,
                    meta_description=(
                        getattr(product, "description", "")[:160]
                        if hasattr(product, "description")
                        else ""
                    ),
                    seo_keywords="",
                )
            )

        if meta_objects:
            ProductMeta.objects.bulk_create(meta_objects, ignore_conflicts=True)
            return len(meta_objects)

        return 0
