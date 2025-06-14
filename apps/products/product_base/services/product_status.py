from apps.core.utils.cache_manager import CacheManager
from rest_framework.response import Response
from rest_framework import status


class ProductStatusService:
    @staticmethod
    def update_status(view, new_status, request, pk=None):
        product = view.get_object()
        previous_status = product.status
        if not previous_status != new_status:
            return Response(
                {
                    "message": f"Status is already in: {new_status}",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                }
            )
        product.status = new_status
        product.save()
        CacheManager.invalidate("product_base", id=product.pk)
        return view.success_response(data=product.status)
