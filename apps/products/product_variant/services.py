import logging
import itertools
import hashlib
import json
from decimal import Decimal
from typing import List, Dict, Optional
from django.db import transaction
from django.core.exceptions import ValidationError
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Sum, Min, Max, Avg, Q, F, Prefetch
from django_redis import get_redis_connection
from apps.products.product_base.models import Product

# from apps.core.utils.cache_manager import CacheManager
from apps.core.utils.cache_key_manager import CacheKeyManager

from .models import (
    ProductVariantType,
    ProductVariantOption,
    ProductVariant,
    ProductVariantImage,
)

CACHE_TTL = getattr(settings, "VARIANTS_CACHE_TTL", 300)
logger = logging.getLogger("variant_performance")


class ProductVariantService:
    """Enhanced service class for product variant operations."""

    CACHE_TIMEOUT = CACHE_TTL
    DETAIL_KEYS_SET = "safetrade:product_variant:detail:keys"

    @staticmethod
    @transaction.atomic
    def bulk_create_variant_types(types_data: List[Dict]) -> List[ProductVariantType]:
        """Bulk create variant types with validation.

        Args:
            types_data (List[Dict]): List of dictionaries containing variant type data

        Returns:
            List[ProductVariantType]: List of created variant types
        """
        created_types = []
        for type_data in types_data:
            # Create the variant type
            variant_type = ProductVariantType.objects.create(
                name=type_data.get("name"),
                slug=type_data.get("slug"),
                sort_order=type_data.get("sort_order", 0),
                is_active=type_data.get("is_active", True),
            )
            created_types.append(variant_type)

        # Clear cache after bulk creation
        cache.delete_pattern("product_variant:types:*")
        return created_types

    @staticmethod
    @transaction.atomic
    def bulk_create_variant_options(
        variant_type_id: int, options_data: List[Dict]
    ) -> List[ProductVariantOption]:
        """Bulk create variant options for a specific variant type.

        Args:
            variant_type_id (int): ID of the variant type
            options_data (List[Dict]): List of dictionaries containing option data

        Returns:
            List[ProductVariantOption]: List of created variant options
        """
        variant_type = ProductVariantType.objects.get(id=variant_type_id)
        created_options = []

        for option_data in options_data:
            option = ProductVariantOption.objects.create(
                variant_type=variant_type,
                value=option_data.get("value"),
                slug=option_data.get("slug"),
                display_value=option_data.get("display_value"),
                color_code=option_data.get("color_code"),
                price_adjustment=option_data.get("price_adjustment", Decimal("0.00")),
                sort_order=option_data.get("sort_order", 0),
                is_active=option_data.get("is_active", True),
            )
            created_options.append(option)

        # Clear cache after bulk creation
        cache.delete_pattern("product_variant:types:*")
        return created_options

    # ==========================================
    # CORE RETRIEVAL METHODS
    # ==========================================

    @staticmethod
    def get_variant_types(active_only: bool = True, with_options: bool = False):
        """Get variant types with improved caching and prefetching."""
        cache_key = CacheKeyManager.make_key(
            "product_variant",
            "types",
            active_only=active_only,
            with_options=with_options,
        )
        logger.info(f"Retrieving variant types with cache key: {cache_key}")
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        qs = ProductVariantType.objects.all()
        if active_only:
            qs = qs.filter(is_active=True)

        if with_options:
            qs = qs.prefetch_related(
                Prefetch(
                    "options",
                    queryset=ProductVariantOption.objects.filter(
                        is_active=True
                    ).order_by("sort_order"),
                )
            )

        result = list(qs.order_by("sort_order"))
        cache.set(cache_key, result, ProductVariantService.CACHE_TIMEOUT)
        return result

    @staticmethod
    def get_product_variants(
        product_id: int,
        active_only: bool = True,
        in_stock_only: bool = False,
        with_options: bool = True,
        with_images: bool = False,
        fields_subset: set = None,
    ):
        """Enhanced variant retrieval with flexible filtering and field selection."""
        cache_key = ProductVariantService._generate_detail_cache_key(
            product_id,
            active_only=active_only,
            in_stock_only=in_stock_only,
            with_options=with_options,
            fields=",".join(sorted(fields_subset)) if fields_subset else "all",
        )

        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        qs = ProductVariant.objects.filter(product_id=product_id)

        if active_only:
            qs = qs.filter(is_active=True)

        if in_stock_only:
            qs = qs.filter(stock_quantity__gt=F("reserved_quantity"))

        # Optimize field selection if subset specified
        if fields_subset:
            required_fields = {"id", "product_id"} | fields_subset
            qs = qs.only(*required_fields)

        # Always select related product for efficiency, but only needed fields
        qs = qs.select_related("product").only(
            "product__id", "product__requires_shipping", "product__price"
        )

        if with_options:
            # Optimize option fields
            option_fields = {
                "id",
                "value",
                "slug",
                "display_value",
                "price_adjustment",
                "variant_type__id",
                "variant_type__name",
                "variant_type__slug",
            }
            qs = qs.prefetch_related(
                Prefetch(
                    "options",
                    queryset=ProductVariantOption.objects.select_related("variant_type")
                    .only(*option_fields)
                    .order_by("variant_type__sort_order", "sort_order"),
                )
            )

        if with_images:
            # Optimize image fields
            image_fields = {"id", "image", "sort_order", "is_primary"}
            qs = qs.prefetch_related(
                Prefetch(
                    "images",
                    queryset=ProductVariantImage.objects.only(*image_fields).order_by(
                        "sort_order"
                    ),
                )
            )

        result = list(qs.order_by("id"))
        cache.set(cache_key, result, ProductVariantService.CACHE_TIMEOUT)
        return result

    @staticmethod
    def _generate_detail_cache_key(product_id: str, **kwargs):

        params = {
            "product_id": str(product_id),
            "active_only": kwargs.get("active_only"),
            "in_stock_only": kwargs.get("in_stock_only"),
            "with_options": kwargs.get("with_options"),
        }

        params_str = json.dumps(params, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:12]

        key = CacheKeyManager.make_key("product_variant", "detail", params=params_hash)
        redis_conn = get_redis_connection("default")
        redis_conn.sadd(ProductVariantService.DETAIL_KEYS_SET, key)
        logger.info(f"Generated cache key: {key} with params: {params}")
        return key

    @staticmethod
    def get_variant_by_options(
        product_id: int, option_ids: List[int]
    ) -> Optional[ProductVariant]:
        """Find variant by exact option combination."""
        if not option_ids:
            return None

        # Sort option_ids for consistent caching
        sorted_option_ids = sorted(option_ids)
        cache_key = CacheKeyManager.make_key(
            "product_variant",
            "options",
            product_id=product_id,
            option_ids="-".join(map(str, sorted_option_ids)),
        )
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        # Find variant with exact option match
        variants = (
            ProductVariant.objects.filter(
                product_id=product_id, is_active=True, options__in=option_ids
            )
            .annotate(option_count=Count("options"))
            .filter(option_count=len(option_ids))
            .prefetch_related("options")
        )

        # Verify exact match (no extra options)
        for variant in variants:
            variant_option_ids = set(variant.options.values_list("id", flat=True))
            if variant_option_ids == set(option_ids):
                cache.set(cache_key, variant, ProductVariantService.CACHE_TIMEOUT)
                return variant

        cache.set(cache_key, None, ProductVariantService.CACHE_TIMEOUT)
        return None

    @staticmethod
    def get_variant_matrix(product_id: int) -> Dict:
        """Enhanced variant matrix with pricing and availability info."""
        cache_key = CacheKeyManager.make_key("variant_matrix", product_id=product_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        variants = (
            ProductVariant.objects.filter(product_id=product_id, is_active=True)
            .prefetch_related("options__variant_type")
            .select_related("product")
        )

        matrix = {}
        for variant in variants:
            # Create sorted key for consistent lookup
            key_parts = []
            options_data = []

            for opt in variant.options.all():
                key_parts.append(f"{opt.variant_type.slug}:{opt.slug}")
                options_data.append(
                    {
                        "id": opt.id,
                        "type_id": opt.variant_type.id,
                        "type": opt.variant_type.name,
                        "type_slug": opt.variant_type.slug,
                        "value": opt.value,
                        "display_value": opt.display_value or opt.value,
                        "slug": opt.slug,
                        "price_adjustment": str(opt.price_adjustment),
                        "color_code": opt.color_code,
                        "image": opt.image.url if opt.image else None,
                    }
                )

            matrix_key = "|".join(sorted(key_parts))

            matrix[matrix_key] = {
                "id": variant.id,
                "sku": variant.sku,
                "price": str(variant.price) if variant.price is not None else None,
                "final_price": (
                    str(variant.final_price)
                    if variant.final_price is not None
                    else None
                ),
                "cost_price": (
                    str(variant.cost_price) if variant.cost_price is not None else None
                ),
                "stock_quantity": variant.stock_quantity,
                "reserved_quantity": variant.reserved_quantity,
                "available_quantity": variant.available_quantity,
                "is_in_stock": variant.is_in_stock,
                "is_low_stock": variant.is_low_stock,
                "low_stock_threshold": variant.low_stock_threshold,
                "weight": str(variant.weight) if variant.weight else None,
                "dimensions": (
                    {
                        "length": (
                            str(variant.dimensions_length)
                            if variant.dimensions_length
                            else None
                        ),
                        "width": (
                            str(variant.dimensions_width)
                            if variant.dimensions_width
                            else None
                        ),
                        "height": (
                            str(variant.dimensions_height)
                            if variant.dimensions_height
                            else None
                        ),
                    }
                    if any(
                        [
                            variant.dimensions_length,
                            variant.dimensions_width,
                            variant.dimensions_height,
                        ]
                    )
                    else None
                ),
                "is_digital": variant.is_digital,
                "requires_shipping": variant.product.requires_shipping,
                "is_backorderable": variant.is_backorderable,
                "expected_restock_date": (
                    variant.expected_restock_date.isoformat()
                    if variant.expected_restock_date
                    else None
                ),
                "escrow_hold_period": variant.escrow_hold_period,
                "requires_inspection": variant.requires_inspection,
                "options": sorted(options_data, key=lambda x: x["type_id"]),
            }

        cache.set(cache_key, matrix, ProductVariantService.CACHE_TIMEOUT)
        return matrix

    # ==========================================
    # VARIANT CREATION METHODS
    # ==========================================

    @staticmethod
    @transaction.atomic
    def create_variant_combination(
        product_id: int,
        option_ids: List[int],
        sku: str,
        validate_uniqueness: bool = True,
        **kwargs,
    ) -> ProductVariant:
        """Create a single variant with enhanced validation."""
        # Validate product exists
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            raise ValidationError(f"Product with id {product_id} does not exist")

        # Validate SKU uniqueness
        if validate_uniqueness and ProductVariant.objects.filter(sku=sku).exists():
            raise ValidationError(f"SKU '{sku}' already exists")

        # Validate options
        options = list(
            ProductVariantOption.objects.filter(
                id__in=option_ids, is_active=True
            ).select_related("variant_type")
        )

        if len(options) != len(option_ids):
            missing_ids = set(option_ids) - set(opt.id for opt in options)
            raise ValidationError(f"Invalid or inactive option IDs: {missing_ids}")

        # Validate unique variant types
        variant_types = [opt.variant_type for opt in options]
        variant_type_ids = [vt.id for vt in variant_types]
        if len(set(variant_type_ids)) != len(variant_type_ids):
            raise ValidationError("Options must belong to different variant types")

        # Check for existing variant with same options
        if validate_uniqueness:
            existing = ProductVariantService.get_variant_by_options(
                product_id, option_ids
            )
            if existing:
                raise ValidationError(
                    f"Variant with these options already exists: {existing.sku}"
                )

        total_adjustment = sum(
            (opt.price_adjustment or Decimal("0.00")) for opt in options
        )

        # 2. Determine your “base” price (could be product.price or product.base_price):
        base_price = getattr(product, "price", None) or product.price

        # 3. Set the variant’s price to base + adjustment:
        kwargs["price"] = base_price + total_adjustment
        # Create variant
        variant = ProductVariant.objects.create(
            product_id=product_id, sku=sku, **kwargs
        )
        variant.options.set(options)

        # Clear caches
        ProductVariantService.invalidate_variant_detail_caches()

        return variant

    @staticmethod
    @transaction.atomic
    def bulk_create_variants(
        product_id: int,
        variant_data: List[Dict],
        validate_uniqueness: bool = True,
        update_cache: bool = True,
    ) -> List[ProductVariant]:
        """Enhanced bulk creation with better validation and error handling."""
        if not variant_data:
            raise ValidationError("No variant data provided")

        # Validate product exists
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            raise ValidationError(f"Product with id {product_id} does not exist")

        created_variants = []
        errors = []

        # Pre-validate all SKUs for uniqueness
        skus = [data.get("sku") for data in variant_data if data.get("sku")]
        if validate_uniqueness and skus:
            existing_skus = set(
                ProductVariant.objects.filter(sku__in=skus).values_list(
                    "sku", flat=True
                )
            )

            if existing_skus:
                raise ValidationError(f"SKUs already exist: {existing_skus}")

        # Bulk fetch all options upfront
        all_option_ids = set()
        for data in variant_data:
            option_ids = data.get("option_combinations", [])
            all_option_ids.update(option_ids)

        options_map = {
            opt.id: opt
            for opt in ProductVariantOption.objects.filter(
                id__in=all_option_ids, is_active=True
            ).select_related("variant_type")
        }

        for i, data in enumerate(variant_data):
            try:
                sku = data.get("sku")
                if not sku:
                    raise ValidationError(f"SKU is required for variant {i}")

                option_ids = data.get("option_combinations", [])
                if not option_ids:
                    raise ValidationError(f"Options are required for variant {i}")

                # Validate options exist
                options = [options_map.get(oid) for oid in option_ids]
                if None in options:
                    missing_ids = [oid for oid in option_ids if oid not in options_map]
                    raise ValidationError(
                        f"Invalid option IDs in variant {i}: {missing_ids}"
                    )

                # Validate unique variant types
                variant_type_ids = [opt.variant_type.id for opt in options]
                if len(set(variant_type_ids)) != len(variant_type_ids):
                    raise ValidationError(f"Duplicate variant types in variant {i}")

                # Set default price
                if "price" not in data or data["price"] is None:
                    data["price"] = (
                        product.base_price if hasattr(product, "base_price") else None
                    )

                # Create variant
                variant_data_clean = {
                    k: v for k, v in data.items() if k != "option_combinations"
                }
                variant = ProductVariant.objects.create(
                    product_id=product_id, **variant_data_clean
                )
                variant.options.set(options)
                created_variants.append(variant)

            except Exception as e:
                errors.append(f"Variant {i} ({data.get('sku', 'unknown')}): {str(e)}")

        if errors:
            # Rollback transaction
            raise ValidationError(f"Errors in bulk creation: {'; '.join(errors)}")

        # Clear caches
        if update_cache:
            ProductVariantService._clear_product_caches(product_id)
            ProductVariantService.update_variant_cache(product_id)

        return created_variants

    @staticmethod
    def generate_all_combinations(
        product_id: int,
        variant_type_options: Dict[int, List[int]],
        base_sku: str = None,
        base_price: Decimal = None,
        sku_separator: str = "-",
    ) -> List[Dict]:
        """Enhanced combination generation with better SKU handling."""
        if not variant_type_options:
            return []

        # Get product for base SKU if not provided
        if not base_sku:
            try:
                product = Product.objects.get(id=product_id)
                base_sku = getattr(product, "sku", f"PROD-{product_id}")
            except Product.DoesNotExist:
                base_sku = f"PROD-{product_id}"

        # Get base price from product if not provided
        if base_price is None:
            try:
                product = Product.objects.get(id=product_id)
                base_price = getattr(product, "base_price", None)
            except Product.DoesNotExist:
                base_price = None

        # Fetch all options with their data
        all_option_ids = []
        for option_list in variant_type_options.values():
            all_option_ids.extend(option_list)

        options_map = {
            opt.id: opt
            for opt in ProductVariantOption.objects.filter(
                id__in=all_option_ids, is_active=True
            ).select_related("variant_type")
        }

        # Generate combinations
        option_groups = []
        variant_type_order = []

        for variant_type_id, option_ids in variant_type_options.items():
            valid_options = [
                options_map[oid] for oid in option_ids if oid in options_map
            ]
            if valid_options:
                option_groups.append(valid_options)
                variant_type_order.append(variant_type_id)

        if not option_groups:
            return []

        combinations = list(itertools.product(*option_groups))
        variant_combos = []

        for combo in combinations:
            # Generate SKU
            slugs = [opt.slug.upper() for opt in combo]
            sku = f"{base_sku}{sku_separator}{sku_separator.join(slugs)}"

            # Calculate price adjustments
            total_adjustment = sum(
                opt.price_adjustment for opt in combo if opt.variant_type.affects_price
            )
            final_price = base_price + total_adjustment if base_price else None

            variant_combos.append(
                {
                    "sku": sku,
                    "option_combinations": [opt.id for opt in combo],
                    "price": final_price,
                    "stock_quantity": 0,
                    "is_active": True,
                    "weight": None,
                    "dimensions_length": None,
                    "dimensions_width": None,
                    "dimensions_height": None,
                }
            )

        return variant_combos

    # ==========================================
    # STOCK MANAGEMENT METHODS
    # ==========================================

    @staticmethod
    @transaction.atomic
    def reserve_stock(variant_id: int, quantity: int) -> bool:
        """Reserve stock for a variant."""
        try:
            variant = ProductVariant.objects.select_for_update().get(id=variant_id)
            if variant.reserve_stock(quantity):
                ProductVariantService._clear_product_caches(variant.product_id)
                return True
            return False
        except ProductVariant.DoesNotExist:
            return False

    @staticmethod
    @transaction.atomic
    def release_stock(variant_id: int, quantity: int) -> bool:
        """Release reserved stock for a variant."""
        try:
            variant = ProductVariant.objects.select_for_update().get(id=variant_id)
            variant.release_stock(quantity)
            ProductVariantService._clear_product_caches(variant.product_id)
            return True
        except ProductVariant.DoesNotExist:
            return False

    @staticmethod
    @transaction.atomic
    def reduce_stock(variant_id: int, quantity: int) -> bool:
        """Reduce actual stock for a variant."""
        try:
            variant = ProductVariant.objects.select_for_update().get(id=variant_id)
            if variant.reduce_stock(quantity):
                ProductVariantService._clear_product_caches(variant.product_id)
                return True
            return False
        except ProductVariant.DoesNotExist:
            return False

    @staticmethod
    @transaction.atomic
    def bulk_update_stock(stock_updates: List[Dict]) -> Dict:
        """Bulk update stock for multiple variants."""
        results = {"success": [], "errors": []}

        for update in stock_updates:
            try:
                variant_id = update["variant_id"]
                action = update["action"]  # 'set', 'add', 'subtract'
                quantity = update["quantity"]

                variant = ProductVariant.objects.select_for_update().get(id=variant_id)

                if action == "set":
                    variant.stock_quantity = quantity
                elif action == "add":
                    variant.stock_quantity += quantity
                elif action == "subtract":
                    variant.stock_quantity = max(0, variant.stock_quantity - quantity)
                else:
                    raise ValueError(f"Invalid action: {action}")

                variant.save(update_fields=["stock_quantity"])
                results["success"].append(variant_id)

                # Clear cache for this product
                ProductVariantService._clear_product_caches(variant.product_id)

            except Exception as e:
                results["errors"].append(
                    {"variant_id": update.get("variant_id"), "error": str(e)}
                )

        return results

    # ==========================================
    # CACHE AND ANALYTICS METHODS
    # ==========================================

    @staticmethod
    @transaction.atomic
    def update_variant_cache(product_id: int) -> Dict:
        """Enhanced cache update with detailed statistics."""
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return {"error": f"Product {product_id} not found"}

        # Get comprehensive stats
        variant_stats = ProductVariant.objects.filter(
            product=product, is_active=True
        ).aggregate(
            total_variants=Count("id"),
            total_stock=Sum("stock_quantity"),
            total_reserved=Sum("reserved_quantity"),
            min_price=Min("price"),
            max_price=Max("price"),
            avg_price=Avg("price"),
            available_variants=Count(
                "id", filter=Q(stock_quantity__gt=F("reserved_quantity"))
            ),
            low_stock_variants=Count(
                "id", filter=Q(stock_quantity__lte=F("low_stock_threshold"))
            ),
            out_of_stock_variants=Count(
                "id", filter=Q(stock_quantity__lte=F("reserved_quantity"))
            ),
        )

        # Get variant types used
        variant_types = list(
            ProductVariantType.objects.filter(
                options__variants__product=product, options__variants__is_active=True
            )
            .distinct()
            .values_list("name", flat=True)
        )

        # Calculate total available stock
        total_available = (variant_stats["total_stock"] or 0) - (
            variant_stats["total_reserved"] or 0
        )

        # Update product fields if they exist
        update_fields = []
        if hasattr(product, "total_variants"):
            product.total_variants = variant_stats["total_variants"] or 0
            update_fields.append("total_variants")

        if hasattr(product, "total_stock"):
            product.total_stock = variant_stats["total_stock"] or 0
            update_fields.append("total_stock")

        if hasattr(product, "available_stock"):
            product.available_stock = max(0, total_available)
            update_fields.append("available_stock")

        if hasattr(product, "min_variant_price"):
            product.min_variant_price = variant_stats["min_price"]
            update_fields.append("min_variant_price")

        if hasattr(product, "max_variant_price"):
            product.max_variant_price = variant_stats["max_price"]
            update_fields.append("max_variant_price")

        if hasattr(product, "has_variants"):
            product.has_variants = (variant_stats["total_variants"] or 0) > 0
            update_fields.append("has_variants")

        if hasattr(product, "has_stock"):
            product.has_stock = total_available > 0
            update_fields.append("has_stock")

        if hasattr(product, "variant_types"):
            product.variant_types = variant_types
            update_fields.append("variant_types")

        if update_fields:
            product.save(update_fields=update_fields)

        # Cache the stats
        stats_cache_key = CacheKeyManager.make_key(
            "product_variant_stats", product_id=product_id
        )
        stats_data = {
            **variant_stats,
            "total_available": total_available,
            "variant_types": variant_types,
        }
        cache.set(stats_cache_key, stats_data, ProductVariantService.CACHE_TIMEOUT)

        return stats_data

    @staticmethod
    def get_variant_stats(product_id: int) -> Dict:
        """Get cached variant statistics."""
        cache_key = CacheKeyManager.make_key(
            "product_variant_stats", product_id=product_id
        )
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        return ProductVariantService.update_variant_cache(product_id)

    # ==========================================
    # UTILITY METHODS
    # ==========================================

    @staticmethod
    def get_variant_template_for_product(variant_type_ids: List[int]) -> Dict:
        """Enhanced template generation with detailed option info."""
        variant_types = (
            ProductVariantType.objects.filter(id__in=variant_type_ids, is_active=True)
            .prefetch_related(
                Prefetch(
                    "options",
                    queryset=ProductVariantOption.objects.filter(
                        is_active=True
                    ).order_by("sort_order"),
                )
            )
            .order_by("sort_order")
        )

        template = {
            "variant_types": [],
            "total_combinations": 1,
            "estimated_storage_mb": 0,
            "has_price_affecting_options": False,
        }

        for vtype in variant_types:
            active_options = vtype.options.all()
            option_count = len(active_options)

            if option_count > 0:
                template["total_combinations"] *= option_count

                # Check if any options affect price
                if vtype.affects_price:
                    template["has_price_affecting_options"] = True

                template["variant_types"].append(
                    {
                        "id": vtype.id,
                        "name": vtype.name,
                        "slug": vtype.slug,
                        "display_type": vtype.display_type,
                        "is_required": vtype.is_required,
                        "affects_price": vtype.affects_price,
                        "affects_inventory": vtype.affects_inventory,
                        "sort_order": vtype.sort_order,
                        "option_count": option_count,
                        "options": [
                            {
                                "id": opt.id,
                                "value": opt.value,
                                "display_value": opt.display_value or opt.value,
                                "slug": opt.slug,
                                "price_adjustment": str(opt.price_adjustment),
                                "color_code": opt.color_code,
                                "image_url": opt.image.url if opt.image else None,
                                "sort_order": opt.sort_order,
                            }
                            for opt in active_options
                        ],
                    }
                )

        # Estimate storage requirements (rough calculation)
        template["estimated_storage_mb"] = round(
            template["total_combinations"] * 0.001, 2
        )

        return template

    @staticmethod
    def validate_variant_combination(product_id: int, option_ids: List[int]) -> Dict:
        """Validate if a variant combination is valid and available."""
        result = {
            "is_valid": False,
            "variant": None,
            "errors": [],
            "warnings": [],
        }

        try:
            # Check if variant exists
            variant = ProductVariantService.get_variant_by_options(
                product_id, option_ids
            )

            if not variant:
                result["errors"].append("No variant found with these options")
                return result

            result["variant"] = {
                "id": variant.id,
                "sku": variant.sku,
                "price": str(variant.price) if variant.price else None,
                "final_price": (
                    str(variant.final_price) if variant.final_price else None
                ),
                "is_in_stock": variant.is_in_stock,
                "available_quantity": variant.available_quantity,
                "is_low_stock": variant.is_low_stock,
            }

            # Check availability
            if not variant.is_active:
                result["errors"].append("Variant is not active")
            elif not variant.is_in_stock:
                if variant.is_backorderable:
                    result["warnings"].append("Item is backordered")
                else:
                    result["errors"].append("Item is out of stock")
            elif variant.is_low_stock:
                result["warnings"].append(
                    f"Low stock: only {variant.available_quantity} remaining"
                )

            result["is_valid"] = len(result["errors"]) == 0

        except Exception as e:
            result["errors"].append(str(e))

        return result

    @staticmethod
    def invalidate_variant_detail_caches():
        from django_redis import get_redis_connection

        redis_conn = get_redis_connection("default")
        # django-redis strips KEY_PREFIX for you
        # cache.delete("safetrade:product_base:list:main")
        logger.info("Deleting detail caches with pattern")
        raw_keys = redis_conn.smembers(ProductVariantService.DETAIL_KEYS_SET)
        decoded_keys = [k.decode("utf-8") for k in raw_keys]
        print(decoded_keys)
        for key in decoded_keys:
            logger.info(f"Deleted single key: {key}")
            cache.delete(key)
            logger.info(f"✅ Deleted {key} list cache keys")

    # ==========================================
    # ASYNC METHOD WRAPPERS
    # ==========================================

    @staticmethod
    def create_variants_async(
        product_id: int, variant_combinations: List[Dict], delay_seconds: int = 0
    ):
        """Async wrapper for variant creation."""
        from .tasks import create_product_variants_task

        if delay_seconds > 0:
            return create_product_variants_task.apply_async(
                args=[product_id, variant_combinations], countdown=delay_seconds
            )
        return create_product_variants_task.delay(product_id, variant_combinations)

    @staticmethod
    def update_variant_cache_async(product_id: int, delay_seconds: int = 5):
        """Async wrapper for cache updates."""
        from .tasks import update_product_variant_cache_task

        if delay_seconds > 0:
            return update_product_variant_cache_task.apply_async(
                args=[product_id], countdown=delay_seconds
            )
        return update_product_variant_cache_task.delay(product_id)

    @staticmethod
    def generate_combinations_async(
        product_id: int,
        variant_type_options: Dict[int, List[int]],
        base_price: Decimal = None,
    ):
        """Async wrapper for combination generation."""
        from .tasks import generate_variant_combinations_task

        return generate_variant_combinations_task.delay(
            product_id, variant_type_options, base_price
        )

    @staticmethod
    @transaction.atomic
    def generate_and_create_variants(
        product_id: int,
        variant_type_options: Dict[int, List[int]],
        base_price: Decimal = None,
        sku_separator: str = "-",
    ) -> List[ProductVariant]:
        """Generate and create all combinations synchronously."""
        try:
            product = Product.objects.get(id=product_id)
            base_sku = getattr(product, "sku", f"PROD-{product_id}")
        except Product.DoesNotExist:
            base_sku = f"PROD-{product_id}"

        # Generate all combinations
        combos = ProductVariantService.generate_all_combinations(
            product_id=product_id,
            variant_type_options=variant_type_options,
            base_sku=base_sku,
            base_price=base_price,
            sku_separator=sku_separator,
        )

        if not combos:
            return []

        # Create variants using bulk_create_variants
        created_variants = ProductVariantService.bulk_create_variants(
            product_id=product_id,
            variant_data=combos,
            validate_uniqueness=True,
            update_cache=True,
        )

        return created_variants

    @staticmethod
    def generate_and_create_variants_async(
        product_id: int,
        variant_type_options: Dict[int, List[int]],
        base_price: Decimal = None,
        sku_separator: str = "-",
        delay_seconds: int = 0,
    ):
        """Async wrapper for generating and creating all variants."""
        from .tasks import generate_and_create_variants_task

        if delay_seconds > 0:
            return generate_and_create_variants_task.apply_async(
                args=[product_id, variant_type_options, base_price, sku_separator],
                countdown=delay_seconds,
            )
        return generate_and_create_variants_task.delay(
            product_id, variant_type_options, base_price, sku_separator
        )

    @staticmethod
    def bulk_stock_update_async(stock_updates: List[Dict], delay_seconds: int = 0):
        """Async wrapper for bulk stock updates."""
        from .tasks import bulk_stock_update_task

        if delay_seconds > 0:
            return bulk_stock_update_task.apply_async(
                args=[stock_updates], countdown=delay_seconds
            )
        return bulk_stock_update_task.delay(stock_updates)

    @staticmethod
    def validate_product_variants_async(product_id: int, delay_seconds: int = 0):
        """Async wrapper for variant validation."""
        from .tasks import validate_product_variants_task

        if delay_seconds > 0:
            return validate_product_variants_task.apply_async(
                args=[product_id], countdown=delay_seconds
            )
        return validate_product_variants_task.delay(product_id)
