import logging
from django.db import models
from django.db.models import Avg, Count, Q, Prefetch
from django.contrib.auth import get_user_model

from django.core.cache import cache
from apps.core.utils.cache_manager import CacheKeyManager, CacheManager
from apps.products.product_base.models import Product
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
        """Base queryset with common optimizations"""
        return Product.objects.select_related(
            "brand",
            "category",
            "condition",
            "seller",
            "seller__profile",  # If you have user profiles
        )

    @staticmethod
    def get_product_detail_queryset(request):
        """Comprehensive queryset for product detail view"""
        from apps.products.product_rating.models import ProductRating

        base_queryset = ProductDetailService.get_base_product_queryset()

        # Prefetch ratings with users and helpfulness votes
        detailed_ratings_prefetch = Prefetch(
            "ratings",
            queryset=ProductRating.objects.filter(is_approved=True)
            .select_related("user")
            .prefetch_related("helpfulness_votes")
            .order_by("-created_at"),
            to_attr="approved_ratings",
        )

        # Prefetch user's own rating if authenticated
        user_rating_prefetch = None
        if request.user.is_authenticated:
            user_rating_prefetch = Prefetch(
                "ratings",
                queryset=ProductRating.objects.filter(
                    user=request.user, is_approved=True
                ).select_related("user"),
                to_attr="user_rating",
            )

        queryset = base_queryset.prefetch_related(
            "images",
            "variants__images",  # If variants have images
            "variants__options",  # If you have variant attributes
            "watchers",
            "meta",
            detailed_ratings_prefetch,
            "rating_aggregate",
            # Related products if you have them
            "category__products",
            "brand__products",
        ).annotate(
            # Comprehensive rating annotations
            avg_rating_db=Avg("ratings__rating", filter=Q(ratings__is_approved=True)),
            ratings_count_db=Count("ratings", filter=Q(ratings__is_approved=True)),
            verified_ratings_count=Count(
                "ratings",
                filter=Q(ratings__is_approved=True, ratings__is_verified_purchase=True),
            ),
            # Rating breakdown
            five_star_count=Count(
                "ratings", filter=Q(ratings__rating=5, ratings__is_approved=True)
            ),
            four_star_count=Count(
                "ratings", filter=Q(ratings__rating=4, ratings__is_approved=True)
            ),
            three_star_count=Count(
                "ratings", filter=Q(ratings__rating=3, ratings__is_approved=True)
            ),
            two_star_count=Count(
                "ratings", filter=Q(ratings__rating=2, ratings__is_approved=True)
            ),
            one_star_count=Count(
                "ratings", filter=Q(ratings__rating=1, ratings__is_approved=True)
            ),
            # User engagement metrics
            watchers_count=Count("watchers", distinct=True),
            total_views=models.F("meta__views_count"),
        )

        # Add authenticated user specific annotations
        if request.user.is_authenticated:
            queryset = queryset.annotate(
                user_has_purchased=Count(
                    "escrow_transactions",
                    filter=Q(
                        escrow_transactions__buyer=request.user,
                        escrow_transactions__status="completed",
                    ),
                ),
            )

        # Add user's rating prefetch if authenticated
        if user_rating_prefetch:
            queryset = queryset.prefetch_related(user_rating_prefetch)

        return queryset

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
