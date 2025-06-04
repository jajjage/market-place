from django.db import models
from django.db.models import Avg, Count, Q, Prefetch
from django.core.cache import cache
from apps.core.utils.cache_key_manager import CacheKeyManager


class BrandQuerySet(models.QuerySet):
    """Custom QuerySet for optimized brand queries"""

    def active(self):
        return self.filter(is_active=True)

    def featured(self):
        return self.filter(is_featured=True, is_active=True)

    def verified(self):
        return self.filter(is_verified=True, is_active=True)

    def with_product_stats(self):
        from apps.products.product_base.models import Product

        """Prefetch product statistics to avoid N+1 queries"""
        return self.prefetch_related(
            Prefetch(
                "products",
                queryset=Product.objects.select_related().filter(is_active=True),
            )
        ).annotate(
            active_product_count=Count("products", filter=Q(products__is_active=True)),
            avg_rating=Avg(
                "products__average_rating", filter=Q(products__is_active=True)
            ),
        )

    def search(self, query):
        """Full-text search across brand fields"""
        return self.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(country_of_origin__icontains=query)
        )

    def with_minimal_data(self):
        """Return only essential fields for lists"""
        return self.only(
            "id",
            "name",
            "slug",
            "logo",
            "country_of_origin",
            "is_verified",
            "is_featured",
            "cached_product_count",
            "cached_average_rating",
        )

    def with_full_data(self):
        """Return all fields with optimized joins"""
        from apps.products.product_base.models import Product

        return self.select_related().prefetch_related(
            "variants",
            Prefetch(
                "products",
                queryset=Product.objects.select_related("category").only(
                    "id", "name", "price", "average_rating", "rating_count"
                ),
            ),
        )

    def popular_brands(self, limit=10):
        """Get popular brands based on product count and ratings"""
        return self.filter(
            cached_product_count__gte=5, cached_average_rating__gte=3.5, is_active=True
        ).order_by("-cached_product_count", "-cached_average_rating")[:limit]


class BrandManager(models.Manager):
    def get_queryset(self):
        return BrandQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def featured(self):
        return self.get_queryset().featured()

    def with_stats(self):
        return self.get_queryset().with_product_stats()


class BrandCacheManager:
    """Centralized cache management for brands"""

    @staticmethod
    def warm_cache_for_brand(brand_id: int):
        """Pre-warm cache for a brand"""
        from .models import Brand
        from .services import BrandService

        try:
            brand = Brand.objects.get(id=brand_id)

            # Warm up commonly accessed data
            brand.get_stats(use_cache=True)
            BrandService.get_brand_analytics(brand_id, days=30)

            # Warm up variants cache
            variants = brand.variants.filter(is_active=True)
            for variant in variants:
                cache_key = CacheKeyManager.make_key(
                    "BRAND_VARIANTS",
                    brand_id=brand_id,
                    locale=f"{variant.language_code}-{variant.region_code}",
                )
                cache.set(cache_key, variant, timeout=3600)

        except Brand.DoesNotExist:
            pass
