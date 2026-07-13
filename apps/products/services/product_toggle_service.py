from django.db import transaction


class ProductToggleService:
    @staticmethod
    @transaction.atomic
    def toggle_active(product):
        product.is_active = not product.is_active
        product.save(
            update_fields=["is_active", "updated_at"]
        )  # Also optimize the save
        return product.is_active

    @staticmethod
    @transaction.atomic
    def toggle_featured(product):
        product.is_featured = not product.is_featured
        product.save(
            update_fields=["is_featured", "updated_at"]
        )  # Also optimize the save
        return product.is_featured

    @staticmethod
    @transaction.atomic
    def toggle_negotiation(product):
        """
        Accepts a product instance and toggles its is_negotiable flag.
        """
        product.is_negotiable = not product.is_negotiable
        product.save(
            update_fields=["is_negotiable", "updated_at"]
        )  # Also optimize the save
        return product.is_negotiable
