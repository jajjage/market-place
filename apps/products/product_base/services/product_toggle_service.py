from apps.core.utils.cache_manager import CacheManager


class ProductToggleService:
    @staticmethod
    def toggle_active(view, request, pk=None):
        product = view.get_object()
        product.is_active = not product.is_active
        product.save()
        CacheManager.invalidate("product_base", id=product.pk)
        return view.success_response(data=product.is_active)

    @staticmethod
    def toggle_featured(view, request, pk=None):
        product = view.get_object()
        product.is_featured = not product.is_featured
        product.save()
        CacheManager.invalidate("product_base", id=product.pk)
        return view.success_response(data=product.is_featured)
