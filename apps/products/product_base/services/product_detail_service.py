from django.core.cache import cache
from apps.core.utils.cache_manager import CacheKeyManager, CacheManager
from apps.products.product_base.models import Product
from apps.products.product_base.serializers import ProductDetailSerializer
from rest_framework import status
import logging

logger = logging.getLogger("products_performance")


class ProductDetailService:
    @staticmethod
    def retrieve_by_shortcode(view, request, *args, **kwargs):
        short_code = kwargs.get("short_code")
        if CacheManager.cache_exists(
            "product_base", "detail_by_shortcode", short_code=short_code
        ):
            cache_key = CacheKeyManager.make_key(
                "product_base", "detail_by_shortcode", short_code=short_code
            )
            cached_data = cache.get(cache_key)
            logger.info(f"Cache HIT for product detail by shortcode: {cache_key}")
            return view.success_response(
                data=cached_data,
                message="product retrieved from cache successfully",
            )

        logger.info(f"Cache MISS for product detail by shortcode: {cache_key}")
        try:
            instance = Product.objects.get(short_code=short_code)
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
        cache.set(cache_key, serialized_data, view.CACHE_TTL)
        logger.info(f"Cached product detail by shortcode: {cache_key}")
        return view.success_response(
            data=serialized_data,
            message="product retrieved successfully",
        )
