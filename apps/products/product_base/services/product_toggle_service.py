from django.db import transaction


class ProductToggleService:
    @staticmethod
    @transaction.atomic
    def toggle_active(view, request, pk=None):
        product = view.get_object()
        product.is_active = not product.is_active
        product.save()
        return view.success_response(data=product.is_active)

    @staticmethod
    @transaction.atomic
    def toggle_featured(view, request, pk=None):
        product = view.get_object()
        product.is_featured = not product.is_featured
        product.save()
        return view.success_response(data=product.is_featured)

    @staticmethod
    @transaction.atomic
    def toggle_negotiation(view, request, pk=None):
        product = view.get_object()
        product.is_negotiable = not product.is_negotiable
        product.save()
        return view.success_response(data=product.is_negotiable)
