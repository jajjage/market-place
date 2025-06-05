from apps.core.utils.cache_manager import CacheKeyManager, CacheManager
from django.core.cache import cache
from apps.products.product_base.serializers import ProductListSerializer


class ProductMyService:
    @staticmethod
    def get_my_products(view, request):
        if CacheManager.cache_exists(
            "product_base", "my_products", user_id=request.user.id
        ):
            cache_key = CacheKeyManager.make_key(
                "product_base", "my_products", user_id=request.user.id
            )
            cached_data = cache.get(cache_key)
            view.logger.info(f"Cache HIT for my products: {cache_key}")
            return view.success_response(data=cached_data)

        queryset = view.get_queryset().filter(seller=request.user)
        status_param = request.query_params.get("status", None)
        if status_param:
            queryset = queryset.filter(status=status_param)
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
        cache_key = CacheKeyManager.make_key(
            "product_base", "my_products", user_id=request.user.id
        )
        cache.set(cache_key, data, view.CACHE_TTL)
        view.logger.info(f"Cached my products: {cache_key}")
        return view.success_response(data=data)
