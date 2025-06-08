# apps/products/services/variants_services.py

import itertools
from django.db import transaction
from django.core.exceptions import ValidationError
from django.conf import settings
from django.core.cache import cache

from typing import List, Dict

from apps.products.product_base.models import Product
from apps.core.utils.cache_manager import CacheManager
from apps.core.utils.cache_key_manager import CacheKeyManager

from .models import (
    ProductVariantType,
    ProductVariantOption,
    ProductVariant,
)

CACHE_TTL = getattr(settings, "VARIANTS_CACHE_TTL", 300)


class ProductVariantService:
    """Service class for product variant operations."""

    CACHE_TIMEOUT = CACHE_TTL  # e.g. 300 seconds (5 minutes)

    @staticmethod
    def get_variant_types(active_only: bool = True):
        """
        Return a QuerySet (cached) of ProductVariantType, optionally filtering to is_active=True.
        """
        cache_key = CacheKeyManager.make_key(
            "product_variant_types", active_only=active_only
        )
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        qs = ProductVariantType.objects.all()
        if active_only:
            qs = qs.filter(is_active=True)

        result = qs.prefetch_related("options").order_by("sort_order")
        cache.set(cache_key, result, ProductVariantService.CACHE_TIMEOUT)
        return result

    @staticmethod
    def get_product_variants(product_id: int, with_options: bool = True):
        """
        Return a list of ProductVariant for a given product_id (cached).
        If with_options=True, do a prefetch on variant options.
        """
        cache_key = CacheKeyManager.make_key(
            "product_variant", "list_product_variants", product_id=product_id
        )
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        qs = ProductVariant.objects.filter(
            product_id=product_id, is_active=True
        ).select_related("product")

        if with_options:
            qs = qs.prefetch_related("options__variant_type")

        result = list(qs)
        cache.set(cache_key, result, ProductVariantService.CACHE_TIMEOUT)
        return result

    @staticmethod
    def get_variant_matrix(product_id: int) -> Dict:
        """
        Build a “matrix” keyed by “type1:slug1|type2:slug2|...” → { id, sku, price, stock, options: […] }.
        Cached per product.
        """
        cache_key = CacheKeyManager.make_key("variant_matrix", product_id=product_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        variants = ProductVariant.objects.filter(
            product_id=product_id, is_active=True
        ).prefetch_related("options__variant_type")

        matrix = {}
        for variant in variants:
            key_parts = []
            for opt in variant.options.all():
                key_parts.append(f"{opt.variant_type.slug}:{opt.slug}")
            joined_key = "|".join(sorted(key_parts))

            matrix[joined_key] = {
                "id": variant.id,
                "sku": variant.sku,
                "price": str(variant.price) if variant.price is not None else None,
                "stock": variant.stock_quantity,
                "options": [
                    {
                        "type": opt.variant_type.name,
                        "value": opt.value,
                        "slug": opt.slug,
                    }
                    for opt in variant.options.all()
                ],
            }

        cache.set(cache_key, matrix, ProductVariantService.CACHE_TIMEOUT)
        return matrix

    @staticmethod
    @transaction.atomic
    def create_variant_combination(
        product_id: int, option_ids: List[int], sku: str, **kwargs
    ) -> ProductVariant:
        """
        Create a single variant for product_id using exactly the provided option_ids.
        Raises ValueError/ValidationError if the option_ids do not correspond to unique variant types.
        """
        options = ProductVariantOption.objects.filter(id__in=option_ids, is_active=True)
        variant_types = set(option.variant_type_id for option in options)

        if len(variant_types) != len(option_ids):
            raise ValueError("Options must belong to different variant types")

        variant = ProductVariant.objects.create(
            product_id=product_id, sku=sku, **kwargs
        )
        variant.options.set(options)

        # Clear any cached “product_variants” for this product (both with and without options).
        CacheManager.invalidate("product_variant", product_id=product_id)

        return variant

    @staticmethod
    @transaction.atomic
    def bulk_create_variants(
        product_id: int, variant_data: List[Dict]
    ) -> List[ProductVariant]:
        """
        Synchronously bulk‐create variants from a list of variant_data dicts.
        Example variant_data item format:
            {
              'sku': 'PROD-001-RED-L',
              'option_combinations': [1, 5],  # two option IDs
              'price': '29.99',
              'stock_quantity': 10,
              'is_active': True
            }
        Returns the list of created ProductVariant instances.
        Raises ValidationError on failure.
        """
        created_variants = []

        for data in variant_data:
            sku = data["sku"]
            if ProductVariant.objects.filter(sku=sku).exists():
                raise ValidationError(f"SKU {sku} already exists")

            option_ids = data.get("option_combinations", [])
            options = ProductVariantOption.objects.filter(
                id__in=option_ids, is_active=True
            )
            if len(options) != len(option_ids):
                raise ValidationError(f"Invalid option IDs in {sku}")

            # Ensure no duplicate variant‐types in that combination:
            variant_types = set(opt.variant_type_id for opt in options)
            if len(variant_types) != len(option_ids):
                raise ValidationError(f"Duplicate variant types in {sku}")

            variant = ProductVariant.objects.create(
                product_id=product_id,
                sku=sku,
                price=data.get("price"),
                stock_quantity=data.get("stock_quantity", 0),
                is_active=data.get("is_active", True),
            )
            variant.options.set(options)
            created_variants.append(variant)

        # Clear caches
        CacheManager.invalidate("product_variant", product_id=product_id)

        return created_variants

    @staticmethod
    def generate_all_combinations(
        product_id: int,
        variant_type_options: Dict[int, List[int]],
        base_sku: str,
        base_price: float = None,
    ) -> List[Dict]:
        """
        Synchronously generate all SKU/option combinations (no DB writes here).
        Returns a list of dicts of the form:
            {
              'sku': 'BASE-RED-L',
              'option_combinations': [1,5],
              'price': base_price,
              'stock_quantity': 0
            }
        """
        groups = list(variant_type_options.values())  # list of lists of IDs
        combos = list(itertools.product(*groups))

        variant_combos = []
        for combo in combos:
            options = ProductVariantOption.objects.filter(id__in=combo, is_active=True)
            slugs = [opt.slug for opt in options]
            sku = f"{base_sku}-{'-'.join(slugs)}".upper()
            variant_combos.append(
                {
                    "sku": sku,
                    "option_combinations": list(combo),
                    "price": base_price,
                    "stock_quantity": 0,
                    "is_active": True,
                }
            )

        return variant_combos

    @staticmethod
    def get_variant_template_for_product(variant_type_ids: List[int]) -> Dict:
        """
        Return a JSON‐serializable template for the front end to generate variants.
        E.g. for each variant_type, return its active options and a count of total combos.
        """
        variant_types = ProductVariantType.objects.filter(
            id__in=variant_type_ids, is_active=True
        ).prefetch_related("options")

        template = {"variant_types": [], "total_combinations": 1}
        for vtype in variant_types:
            active_opts = vtype.options.filter(is_active=True)
            template["variant_types"].append(
                {
                    "id": vtype.id,
                    "name": vtype.name,
                    "slug": vtype.slug,
                    "options": [
                        {"id": opt.id, "value": opt.value, "slug": opt.slug}
                        for opt in active_opts
                    ],
                }
            )
            template["total_combinations"] *= active_opts.count()

        return template

    # ───────────────
    # NEW SYNC “CACHE UPDATE” METHOD
    # ───────────────
    @staticmethod
    @transaction.atomic
    def update_variant_cache(product_id: int) -> None:
        """
        Recompute and save variant‐level stats on the Product model (and/or a cache table).
        Stats include:
          - total_variants
          - total_stock
          - min_price, max_price, avg_price
          - available_variants (stock > 0)
          - has_variants, has_stock
          - variant_types list
        """
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return

        stats = ProductVariant.objects.filter(
            product=product, is_active=True
        ).aggregate(
            total_variants_sum="Count('id')",
            total_stock_sum="Sum('stock_quantity')",
            min_price="Min('price')",
            max_price="Max('price')",
            avg_price="Avg('price')",
            available_variants_sum="Count('id', filter=Q(stock_quantity__gt=0))",
        )

        # We cannot use string‐key names in aggregate; do it explicitly
        from django.db.models import Count, Sum, Min, Max, Avg, Q

        stats = ProductVariant.objects.filter(
            product=product, is_active=True
        ).aggregate(
            total_variants=Count("id"),
            total_stock=Sum("stock_quantity"),
            min_price=Min("price"),
            max_price=Max("price"),
            avg_price=Avg("price"),
            available_variants=Count("id", filter=Q(stock_quantity__gt=0)),
        )

        variant_types = (
            ProductVariantType.objects.filter(
                options__variants__product=product, options__variants__is_active=True
            )
            .distinct()
            .values_list("name", flat=True)
        )

        product.total_variants = stats["total_variants"] or 0
        product.total_stock = stats["total_stock"] or 0
        product.min_variant_price = stats["min_price"]
        product.max_variant_price = stats["max_price"]
        product.avg_variant_price = stats["avg_price"]
        product.available_variants = stats["available_variants"] or 0
        product.has_variants = (stats["total_variants"] or 0) > 0
        product.has_stock = (stats["total_stock"] or 0) > 0
        product.variant_types = list(variant_types)

        product.save(
            update_fields=[
                "total_variants",
                "total_stock",
                "min_variant_price",
                "max_variant_price",
                "avg_variant_price",
                "available_variants",
                "has_variants",
                "has_stock",
                "variant_types",
            ]
        )

    # ───────────────────────────────────────────────────────
    # NEW SYNC “CREATE VARIANTS” METHOD (just wraps bulk_create_variants)
    # ───────────────────────────────────────────────────────
    @staticmethod
    @transaction.atomic
    def create_variants(
        product_id: int, variant_combinations: List[Dict]
    ) -> List[ProductVariant]:
        """
        Synchronously create variants (just a thin wrapper around bulk_create_variants).
        This is here so Celery tasks can call it.
        """
        return ProductVariantService.bulk_create_variants(
            product_id, variant_combinations
        )

    # ──────────────────────────────────────────────────────────────
    # NEW SYNC “GENERATE & CREATE ALL COMBINATIONS” METHOD
    # ──────────────────────────────────────────────────────────────
    @staticmethod
    @transaction.atomic
    def generate_and_create_variants(
        product_id: int,
        variant_type_options: Dict[int, List[int]],
        base_price: float = None,
    ) -> List[ProductVariant]:
        """
        1) Generate all combos via generate_all_combinations()
        2) Bulk‐create via bulk_create_variants()
        3) Update the cache via update_variant_cache()
        Returns the list of created ProductVariant instances.
        """
        base_sku = (
            Product.objects.get(id=product_id).sku
            if hasattr(Product, "sku")
            else f"PROD-{product_id}"
        )
        combos = ProductVariantService.generate_all_combinations(
            product_id, variant_type_options, base_sku, base_price
        )
        created = ProductVariantService.bulk_create_variants(product_id, combos)
        # Once they exist, recalc cache
        ProductVariantService.update_variant_cache(product_id)
        return created

    # ────────────────────────────
    # ASYNC “WRAPPERS” (lazy imports)
    # ────────────────────────────
    @staticmethod
    def create_variants_async(
        product_id: int, variant_combinations: List[Dict], delay_seconds: int = 0
    ):
        """
        Enqueue a background task that simply calls create_variants() & update_variant_cache().
        """
        from .tasks import create_product_variants_task

        if delay_seconds > 0:
            return create_product_variants_task.apply_async(
                args=[product_id, variant_combinations], countdown=delay_seconds
            )
        return create_product_variants_task.delay(product_id, variant_combinations)

    @staticmethod
    def update_variant_cache_async(product_id: int, delay_seconds: int = 5):
        """
        Enqueue a background task that calls update_variant_cache().
        Default: wait 5 seconds, then run.
        """
        from tasks import update_product_variant_cache_task

        if delay_seconds > 0:
            return update_product_variant_cache_task.apply_async(
                args=[product_id], countdown=delay_seconds
            )
        return update_product_variant_cache_task.delay(product_id)

    @staticmethod
    def generate_combinations_async(
        product_id: int,
        variant_type_options: Dict[int, List[int]],
        base_price: float = None,
    ):
        """
        Enqueue a background task that calls generate_and_create_variants().
        Returns the AsyncResult.
        """
        from .tasks import generate_variant_combinations_task

        return generate_variant_combinations_task.delay(
            product_id, variant_type_options, base_price
        )

    @staticmethod
    def bulk_create_variants_async(self, variant_payload: Dict):
        """
        Enqueue a background task that calls bulk_create_variants() and then update cache.
        `variant_payload` should be { "product_id": <int>, "variant_combinations": [ … ] }.
        """
        from .tasks import bulk_create_product_variants_task

        return bulk_create_product_variants_task.delay(variant_payload)
