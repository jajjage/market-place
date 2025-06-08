# apps/breadcrumbs/services.py (Conceptual changes)
import time
import logging
from typing import List, Dict, Any
from django.db import transaction, models
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.contrib.contenttypes.models import ContentType

# Assuming you have CacheKeyManager and CacheManager
from apps.core.utils.cache_key_manager import CacheKeyManager
from apps.core.utils.cache_manager import CacheManager
from apps.products.product_base.models import Product
from .models import Breadcrumb

logger = logging.getLogger("breadcrumbs_performance")


class BreadcrumbService:
    """Service class to handle breadcrumb business logic and complex queries."""

    # B. Generalizing `bulk_create_breadcrumbs`
    @staticmethod
    def bulk_create_breadcrumbs(
        obj: models.Model, breadcrumb_data: List[Dict[str, Any]]
    ) -> List[Breadcrumb]:
        """
        Bulk create breadcrumbs for a specific object.
        Deletes existing breadcrumbs for this object before creating new ones.
        """
        start_time = time.time()
        content_type = ContentType.objects.get_for_model(obj)

        # Convert UUID to string for storage
        object_id_str = str(obj.pk)

        try:
            with transaction.atomic():
                # Delete existing breadcrumbs for this specific object
                Breadcrumb.objects.filter(
                    content_type=content_type,
                    object_id=object_id_str,  # Use string version
                ).delete()

                breadcrumbs_to_create = []
                for i, data in enumerate(breadcrumb_data):
                    breadcrumbs_to_create.append(
                        Breadcrumb(
                            content_type=content_type,
                            object_id=object_id_str,  # Use string version
                            name=data["name"],
                            href=data["href"],
                            order=data.get("order", i),
                        )
                    )

                created_breadcrumbs = Breadcrumb.objects.bulk_create(
                    breadcrumbs_to_create
                )

                # Update cache operations to use string ID
                CacheManager.invalidate_key(
                    "breadcrumb",
                    "object",
                    object_id=object_id_str,  # Use string version
                )

                cache_key = CacheKeyManager.make_key(
                    "breadcrumb",
                    "object",
                    object_id=object_id_str,  # Use string version
                )
                cache.set(cache_key, list(created_breadcrumbs), 3600)
                end_time = time.time()
                logger.info(
                    f"Bulk created {len(created_breadcrumbs)} breadcrumbs for {content_type.app_label}.{content_type.model} ID {obj.pk} in {(end_time - start_time) * 1000:.2f}ms"
                )
                return created_breadcrumbs

        except Exception as e:
            logger.error(
                f"Error bulk creating breadcrumbs for {content_type.app_label}.{content_type.model} ID {obj.pk}: {str(e)}"
            )
            raise ValidationError(f"Failed to create breadcrumbs: {str(e)}")

    @staticmethod
    def update_breadcrumb(breadcrumb_id: int, data: Dict[str, Any]) -> Breadcrumb:
        """
        Update a single breadcrumb segment identified by its ID.
        Invalidates the cache for the associated content object.
        """
        try:
            # Fetch the breadcrumb along with its content_type to get app_label and model name
            breadcrumb = Breadcrumb.objects.select_related("content_type").get(
                id=breadcrumb_id
            )

            # Store old content_type and object_id before potential changes,
            # though typically the content_object itself won't change for a breadcrumb segment.
            # We need these to invalidate the correct cache.
            old_content_type = breadcrumb.content_type
            old_object_id = breadcrumb.object_id

            for field, value in data.items():
                if hasattr(breadcrumb, field):
                    setattr(breadcrumb, field, value)

            breadcrumb.save()

            # Invalidate cache for the content object this breadcrumb belongs to
            CacheManager.invalidate_key(
                "breadcrumb",
                "object",
                object_id=old_object_id,
            ),

            logger.info(
                f"Updated breadcrumb {breadcrumb_id} for {old_content_type.model} ID {old_object_id}"
            )
            return breadcrumb

        except Breadcrumb.DoesNotExist:
            logger.error(f"Breadcrumb with ID {breadcrumb_id} not found for update.")
            raise ValidationError("Breadcrumb not found")
        except Exception as e:
            logger.error(f"Error updating breadcrumb {breadcrumb_id}: {str(e)}")
            raise ValidationError(f"Failed to update breadcrumb: {str(e)}")

    @staticmethod
    def delete_breadcrumb(breadcrumb_id: int):
        """
        Delete a single breadcrumb segment identified by its ID.
        Invalidates the cache for the associated content object.
        """
        try:
            # Fetch the breadcrumb along with its content_type to get app_label and model name
            breadcrumb = Breadcrumb.objects.select_related("content_type").get(
                id=breadcrumb_id
            )

            content_type = breadcrumb.content_type
            object_id = breadcrumb.object_id

            breadcrumb.delete()

            # Invalidate cache for the content object this breadcrumb belonged to
            CacheManager.invalidate_key(
                "breadcrumb",
                "object",
                object_id=object_id,
            ),

            logger.info(
                f"Deleted breadcrumb {breadcrumb_id} for {content_type.model} ID {object_id}"
            )

        except Breadcrumb.DoesNotExist:
            logger.error(f"Breadcrumb with ID {breadcrumb_id} not found for deletion.")
            raise ValidationError("Breadcrumb not found")
        except Exception as e:
            logger.error(f"Error deleting breadcrumb {breadcrumb_id}: {str(e)}")
            raise ValidationError(f"Failed to delete breadcrumb: {str(e)}")

    # For now, let's focus on get and bulk_create.

    # D. New methods to generate breadcrumbs for different object types
    @staticmethod
    def get_breadcrumbs_for_object(obj: models.Model) -> List[Dict[str, Any]]:
        """
        Get breadcrumbs for a specific object (Product, Transaction, User, etc.) with caching.
        Now leverages CategoryService for dynamic category breadcrumbs.
        """
        start_time = time.time()
        content_type = ContentType.objects.get_for_model(obj)

        # Check cache first
        if CacheManager.cache_exists("breadcrumb", "object", object_id=obj.pk):
            cache_key = CacheKeyManager.make_key(
                "breadcrumb", "object", object_id=obj.pk
            )
            cached_breadcrumbs = cache.get(cache_key)
            if cached_breadcrumbs:
                logger.info(
                    f"Retrieved breadcrumbs from cache for {content_type.app_label}.{content_type.model} ID {obj.pk}"
                )
                return cached_breadcrumbs

        # Generate breadcrumbs dynamically based on object type
        breadcrumbs = []

        if isinstance(obj, Product):
            breadcrumbs = BreadcrumbService._generate_product_breadcrumbs(obj)
        else:
            # Fallback to database stored breadcrumbs for other objects
            breadcrumbs = list(
                Breadcrumb.objects.filter(content_type=content_type, object_id=obj.pk)
                .values("name", "href", "order")
                .order_by("order")
            )

        # Cache the result
        cache_key = CacheKeyManager.make_key("breadcrumb", "object", object_id=obj.pk)
        cache.set(cache_key, breadcrumbs, 3600)

        end_time = time.time()
        logger.info(
            f"Generated {len(breadcrumbs)} breadcrumbs for {content_type.app_label}.{content_type.model} ID {obj.pk} in {(end_time - start_time) * 1000:.2f}ms"
        )
        return breadcrumbs

    @staticmethod
    def _generate_product_breadcrumbs(product) -> List[Dict[str, Any]]:
        """
        Generate breadcrumbs for a product using CategoryService.
        """
        breadcrumbs = [{"name": "TrustLock", "href": "/", "order": 0}]

        if hasattr(product, "category") and product.category:
            # Use CategoryService to get the category breadcrumb path
            from apps.categories.services import CategoryService

            category_breadcrumbs = CategoryService.get_breadcrumb_path(
                product.category.id
            )

            # Convert category breadcrumbs to breadcrumb format
            for i, cat_breadcrumb in enumerate(category_breadcrumbs):
                breadcrumbs.append(
                    {
                        "name": cat_breadcrumb["name"],
                        "href": f"/explore?category={cat_breadcrumb['slug']}",
                        "order": i + 1,
                    }
                )

        # Add the product itself as the last breadcrumb
        breadcrumbs.append(
            {
                "name": product.title,
                "href": product.get_absolute_url(),
                "order": len(breadcrumbs),
            }
        )

        return breadcrumbs

    @staticmethod
    def generate_breadcrumbs_for_product(product) -> List[Breadcrumb]:
        """
        Generates and saves breadcrumbs for a Product in the database.
        This is now primarily for backward compatibility or when you need persistent storage.
        """
        breadcrumbs_data = BreadcrumbService._generate_product_breadcrumbs(product)
        return BreadcrumbService.bulk_create_breadcrumbs(product, breadcrumbs_data)

    @staticmethod
    def get_or_generate_breadcrumbs(
        obj: models.Model, force_db_storage: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Unified method to get breadcrumbs.
        For products, generates dynamically unless force_db_storage is True.
        For other objects, uses database storage.
        """
        if isinstance(obj, Product) and not force_db_storage:
            # Generate dynamically for products (leverages CategoryService caching)
            return BreadcrumbService._generate_product_breadcrumbs(obj)
        else:
            # Use database storage with caching
            return BreadcrumbService.get_breadcrumbs_for_object(obj)

    @staticmethod
    def generate_breadcrumbs_for_transaction(transaction) -> List[Breadcrumb]:
        """
        Generates and saves breadcrumbs for a Transaction.
        You'll need to define how your Transaction model's get_absolute_url() works.
        """
        breadcrumbs = [
            {"name": "TrustLock", "href": "/", "order": 0},
            {"name": "My Transactions", "href": "/transactions/", "order": 1},
            {
                "name": f"Transaction #{transaction.id}",
                "href": transaction.get_absolute_url(),
                "order": 2,
            },
            # You might add more steps based on the transaction's status or sub-pages
            # E.g., if on a dispute page for this transaction:
            # {"name": "View Details", "href": transaction.get_absolute_url(), "order": 3},
            # {"name": "Dispute Resolution", "href": f"/transactions/{transaction.id}/dispute/", "order": 4},
        ]
        return BreadcrumbService.bulk_create_breadcrumbs(transaction, breadcrumbs)

    @staticmethod
    def generate_breadcrumbs_for_dispute(dispute) -> List[Breadcrumb]:
        """
        Generates and saves breadcrumbs for a Dispute.
        Assumes dispute has a get_absolute_url() and possibly a link to its transaction.
        """
        breadcrumbs = [
            {"name": "TrustLock", "href": "/", "order": 0},
            {"name": "My Disputes", "href": "/disputes/", "order": 1},
        ]
        # Link to the parent transaction if applicable
        if hasattr(dispute, "transaction") and dispute.transaction:
            breadcrumbs.append(
                {
                    "name": f"Transaction #{dispute.transaction.id}",
                    "href": dispute.transaction.get_absolute_url(),
                    "order": 2,
                }
            )
            breadcrumbs.append(
                {
                    "name": f"Dispute #{dispute.id}",
                    "href": dispute.get_absolute_url(),
                    "order": 3,
                }
            )
        else:
            breadcrumbs.append(
                {
                    "name": f"Dispute #{dispute.id}",
                    "href": dispute.get_absolute_url(),
                    "order": 2,
                }
            )

        return BreadcrumbService.bulk_create_breadcrumbs(dispute, breadcrumbs)

    @staticmethod
    def generate_breadcrumbs_for_user_profile(user_profile) -> List[Breadcrumb]:
        """
        Generates and saves breadcrumbs for a User Profile.
        Assumes user_profile has a get_absolute_url().
        """
        breadcrumbs = [
            {"name": "TrustLock", "href": "/", "order": 0},
            {"name": "My Account", "href": "/account/", "order": 1},
            {
                "name": "Profile Settings",
                "href": user_profile.get_absolute_url(),
                "order": 2,
            },
            # Add more specific profile sub-pages here if needed, e.g., /account/settings/security/
        ]
        return BreadcrumbService.bulk_create_breadcrumbs(user_profile, breadcrumbs)
