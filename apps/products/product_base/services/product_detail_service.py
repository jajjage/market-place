import logging
from django.db.models import Prefetch, Avg, Count, Q, F, Exists, OuterRef, Value
from apps.products.product_base.models import Product
from apps.products.product_rating.models import ProductRating
from apps.products.product_detail.models import ProductDetail  # your “detail” model
from apps.products.product_image.models import ProductImage
from apps.products.product_variant.models import ProductVariant
from apps.products.product_watchlist.models import ProductWatchlistItem
from apps.transactions.models import EscrowTransaction
from django.contrib.auth import get_user_model

from django.core.cache import cache
from apps.core.utils.cache_manager import CacheKeyManager, CacheManager
from apps.products.product_base.serializers import ProductDetailSerializer
from rest_framework import status


# from apps.products.product_metadata.services import ProductMetaService

logger = logging.getLogger("products_performance")


User = get_user_model()


class ProductDetailService:
    @staticmethod
    def retrieve_by_shortcode(view, request, *args, **kwargs):
        short_code = kwargs.get("short_code")
        if CacheManager.cache_exists(
            "product_base", "detail_by_shortcode", short_code=short_code
        ):
            logger.info(f"Retrieving product by shortcode: {short_code}")
            cache_key = CacheKeyManager.make_key(
                "product_base", "detail_by_shortcode", short_code=short_code
            )
            cached_data = cache.get(cache_key)
            logger.info(f"Cache HIT for product detail by shortcode: {cache_key}")
            return view.success_response(
                data=cached_data,
                message="product retrieved from cache successfully",
            )

        try:
            # Use the optimized queryset instead of simple get()
            instance = ProductDetailService.get_product_detail_queryset(request).get(
                short_code=short_code
            )
        except Product.DoesNotExist:
            logger.warning(f"Product not found by shortcode: {short_code}")
            return view.error_response(
                message="product not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        serializer = ProductDetailSerializer(instance, context={"request": request})
        serialized_data = serializer.data
        cache_key = CacheKeyManager.make_key(
            "product_base", "detail_by_shortcode", short_code=short_code
        )

        logger.info(f"Cache MISS for product detail by shortcode: {cache_key}")
        cache.set(cache_key, serialized_data, view.CACHE_TTL)
        logger.info(f"Cached product detail by shortcode: {cache_key}")
        return view.success_response(
            data=serialized_data,
            message="product retrieved successfully",
        )

    @staticmethod
    def invalidate_product_cache(short_code):
        """Invalidate cached product data by short_code"""
        print(f"Invalidating product cache by shortcode: {short_code}")
        CacheManager.invalidate_key(
            "product_base", "detail_by_shortcode", short_code=short_code
        )

    @staticmethod
    def get_base_product_queryset():
        return Product.objects.select_related(
            "brand",
            "category",
            "condition",
            "seller",
            "seller__profile",
            "meta",
        )

    @staticmethod
    def get_product_detail_queryset(request):
        base = ProductDetailService.get_base_product_queryset()

        # Approved ratings
        ratings_qs = ProductRating.objects.filter(is_approved=True).select_related(
            "user"
        )
        detailed_ratings = Prefetch(
            "ratings",
            queryset=ratings_qs.order_by("-created_at"),
            to_attr="approved_ratings",
        )

        # This user's own rating
        user_rating = None
        watch_prefetch = None
        annotations = {}
        # Watchlist items for this user
        if request.user.is_authenticated:
            watch_prefetch = Prefetch(
                "watchers",
                queryset=ProductWatchlistItem.objects.filter(user=request.user),
                to_attr="prefetched_watchlist",
            )

            user_rating = Prefetch(
                "ratings",
                queryset=ratings_qs.filter(user=request.user),
                to_attr="user_rating",
            )

        # ProductDetail extras
        details_prefetch = Prefetch(
            "product_details",
            queryset=ProductDetail.objects.select_related("template"),
            to_attr="prefetched_details",
        )

        # Primary image only
        primary_image = Prefetch(
            "images",
            queryset=ProductImage.objects.filter(is_active=True, is_primary=True),
            to_attr="primary_images",
        )

        # Variants + their options/images
        variant_opts = Prefetch("options", to_attr="prefetched_variant_options")
        variant_imgs = Prefetch("images", to_attr="prefetched_variant_images")
        variant_prefetch = Prefetch(
            "variants",
            queryset=ProductVariant.objects.prefetch_related(
                variant_opts, variant_imgs
            ),
            to_attr="prefetched_variants",
        )
        prefetches = [
            detailed_ratings,
            details_prefetch,
            primary_image,
            variant_prefetch,
        ]

        if user_rating:
            prefetches.append(user_rating)
        if watch_prefetch:
            prefetches.append(watch_prefetch)

        base = base.prefetch_related(*prefetches)

        annotations = {
            "avg_rating_db": Avg(
                "ratings__rating", filter=Q(ratings__is_approved=True)
            ),
            "ratings_count_db": Count("ratings", filter=Q(ratings__is_approved=True)),
            "verified_ratings_count": Count(
                "ratings",
                filter=Q(ratings__is_approved=True, ratings__is_verified_purchase=True),
            ),
            "watchers_count": Count("watchers", distinct=True),
            "total_views": F("meta__views_count"),
        }

        if request.user.is_authenticated:
            annotations["user_has_purchased"] = Exists(
                EscrowTransaction.objects.filter(
                    product=OuterRef("pk"), seller=request.user
                )
            )
        else:
            annotations["user_has_purchased"] = Value(False)

        return base.annotate(**annotations)

    @staticmethod
    def get_related_products_queryset(product):
        """Get related products for detail view"""
        return (
            Product.objects.filter(
                Q(category=product.category) | Q(brand=product.brand), is_active=True
            )
            .exclude(id=product.id)
            .select_related("brand", "category", "seller")
            .prefetch_related("images", "rating_aggregate")
            .annotate(
                avg_rating_db=Avg(
                    "ratings__rating", filter=Q(ratings__is_approved=True)
                ),
                ratings_count_db=Count("ratings", filter=Q(ratings__is_approved=True)),
            )
            .order_by("-created_at")[:10]
        )
