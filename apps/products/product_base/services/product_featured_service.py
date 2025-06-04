from apps.core.utils.cache_manager import CacheKeyManager
from django.core.cache import cache
from apps.products.product_base.serializers import ProductListSerializer


class ProductFeaturedService:
    @staticmethod
    def get_featured(view, request):
        cache_key = CacheKeyManager.make_key("product", "featured")
        cached_data = cache.get(cache_key)
        if cached_data:
            view.logger.info(f"Cache HIT for featured products: {cache_key}")
            return view.success_response(data=cached_data)
        queryset = view.get_queryset().filter(is_featured=True, is_active=True)
        page = view.paginate_queryset(queryset)
        if page is not None:
            serializer = ProductListSerializer(
                page, many=True, context={"request": request}
            )
            data = view.get_paginated_response(serializer.data).data
        else:
            serializer = ProductListSerializer(
                queryset, many=True, context={"request": request}
            )
            data = serializer.data
        cache.set(cache_key, data, view.CACHE_TTL)
        view.logger.info(f"Cached featured products: {cache_key}")
        return view.success_response(data=data)
