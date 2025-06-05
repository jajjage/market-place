from apps.core.utils.cache_manager import CacheKeyManager
from django.core.cache import cache
from rest_framework.response import Response
from apps.products.product_condition.services import ProductConditionService as PCS
from apps.products.product_base.serializers import ProductListSerializer
from apps.products.product_condition.serializers import ProductConditionListSerializer


class ProductConditionService:
    @staticmethod
    def by_condition(view, request, condition_id=None):
        cache_key = CacheKeyManager.make_key(
            "base", "by_condition", condition_id=condition_id
        )
        cached_data = cache.get(cache_key)
        if cached_data:
            view.logger.info(f"Cache HIT for by_condition: {cache_key}")
            return Response(cached_data, status=200)
        filters = {}
        for param in [
            "price_min",
            "price_max",
            "brand",
            "category",
            "in_stock",
            "rating_min",
        ]:
            if param in request.query_params:
                filters[param] = request.query_params[param]
        result = PCS.get_condition_with_products(
            condition_id=int(condition_id), filters=filters
        )
        if not result:
            return Response({"detail": "Condition not found or inactive."}, status=404)
        condition_obj = result["condition"]
        product_qs = result["products"]
        cond_data = ProductConditionListSerializer(condition_obj).data
        serializer = ProductListSerializer(product_qs, many=True)
        products_data = serializer.data
        data = {"condition": cond_data, "products": products_data}
        cache.set(cache_key, data, view.CACHE_TTL)
        view.logger.info(f"Cached by_condition: {cache_key}")
        return Response(data, status=200)
