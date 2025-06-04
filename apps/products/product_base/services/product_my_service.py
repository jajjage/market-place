from apps.core.utils.cache_manager import CacheKeyManager
from django.core.cache import cache
from ..serializers import ProductListSerializer


class ProductMyService:
    @staticmethod
    def get_my_products(view, request):
        cache_key = CacheKeyManager.make_key(
            "product", "my_products", user_id=request.user.id
        )
        cached_data = cache.get(cache_key)
        if cached_data:
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
        cache.set(cache_key, data, view.CACHE_TTL)
        view.logger.info(f"Cached my products: {cache_key}")
        return view.success_response(data=data)
