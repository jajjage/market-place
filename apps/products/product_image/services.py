# services/image_service.py
import time
import logging
import os
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional
from django.db import transaction
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from PIL import Image
import mimetypes
from apps.core.utils.cache_key_manager import CacheKeyManager
from apps.core.utils.cache_manager import CacheManager
from apps.products.product_base.services.product_list_service import ProductListService
from apps.products.product_image.models import ProductImageVariant, ProductImage

logger = logging.getLogger("images_performance")


class ProductImageService:
    """
    Centralized service for Product Image operations with caching and optimization
    """

    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    @staticmethod
    def get_product_images(
        product_id: uuid, include_inactive: bool = False
    ) -> List["ProductImage"]:
        """Get all images for a product with caching"""
        if CacheManager.cache_exists("product_image", "list", product_id=product_id):
            cache_key = CacheKeyManager.make_key(
                "product_image", "list", product_id=product_id
            )
            try:
                cached_images = cache.get(cache_key)
                if cached_images is not None:
                    logger.info(f"Cache hit for product {product_id} images")
                    logger.debug(
                        f"Returning {len(cached_images)} cached images for product {product_id}"
                    )
                    return cached_images
            except Exception as e:
                logger.warning(
                    f"Cache retrieval failed for product {product_id}: {str(e)}"
                )

        start_time = time.time()

        queryset = ProductImage.objects.filter(product_id=product_id)
        if not include_inactive:
            queryset = queryset.filter(is_active=True)

        images = list(queryset.select_related("product").order_by("display_order"))

        cache_key = CacheKeyManager.make_key(
            "product_image", "list", product_id=product_id
        )
        # Cache for 1 hour
        cache.set(cache_key, images, 3600)

        duration = (time.time() - start_time) * 1000
        logger.info(
            f"Fetched {len(images)} images for product {product_id} in {duration:.2f}ms"
        )

        return images

    @staticmethod
    def upload_image(uploaded_file, product_id: int, variant_name: str = None) -> Dict:
        """
        Upload image to local storage and return contracted URL
        """
        start_time = time.time()

        try:
            # Validate file
            validation_result = ProductImageService._validate_image_file(uploaded_file)
            if not validation_result["valid"]:
                raise ValueError(validation_result["error"])

            # Generate unique filename
            file_extension = os.path.splitext(uploaded_file.name)[1].lower()
            unique_filename = f"{uuid.uuid4().hex}{file_extension}"

            # Create directory structure: products/images/{product_id}/
            upload_path = f"products/images/{product_id}/"
            full_path = os.path.join(upload_path, unique_filename)

            # Save file to local storage
            saved_path = default_storage.save(
                full_path, ContentFile(uploaded_file.read())
            )

            # Generate contracted URL
            image_url = ProductImageService._generate_contracted_url(saved_path)

            # Get image dimensions for variant processing
            dimensions = ProductImageService._get_image_dimensions(saved_path)

            duration = (time.time() - start_time) * 1000
            logger.info(
                f"Uploaded image {unique_filename} for product {product_id} in {duration:.2f}ms"
            )
            return {
                "success": True,
                "image_url": image_url,
                "file_path": saved_path,
                "dimensions": dimensions,
                "file_size": uploaded_file.size,
                "filename": unique_filename,
            }

        except Exception as e:
            logger.error(f"Image upload failed for product {product_id}: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def upload_image_async(uploaded_file, product_id: int, variant_name: str = None):
        """Async version for handling multiple uploads"""
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            return loop.run_in_executor(
                executor,
                ProductImageService.upload_image,
                uploaded_file,
                product_id,
                variant_name,
            )

    @staticmethod
    def _validate_image_file(uploaded_file) -> Dict:
        """Validate uploaded image file"""
        # Check file size
        if uploaded_file.size > ProductImageService.MAX_FILE_SIZE:
            return {
                "valid": False,
                "error": f"File size exceeds {ProductImageService.MAX_FILE_SIZE // (1024 * 1024)}MB limit",
            }

        # Check file extension
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()
        if file_extension not in ProductImageService.ALLOWED_EXTENSIONS:
            return {
                "valid": False,
                "error": f'Invalid file type. Allowed: {", ".join(ProductImageService.ALLOWED_EXTENSIONS)}',
            }

        # Check MIME type
        mime_type, _ = mimetypes.guess_type(uploaded_file.name)
        if not mime_type or not mime_type.startswith("image/"):
            return {"valid": False, "error": "Invalid image file"}

        # Validate image content by opening with PIL
        try:
            uploaded_file.seek(0)  # Reset file pointer
            with Image.open(uploaded_file) as img:
                img.verify()  # Verify it's a valid image
            uploaded_file.seek(0)  # Reset for actual reading
        except Exception:
            return {"valid": False, "error": "Corrupted or invalid image file"}

        return {"valid": True}

    @staticmethod
    def _get_image_dimensions(file_path: str) -> Dict:
        """Get image dimensions"""
        try:
            full_path = os.path.join(settings.MEDIA_ROOT, file_path)
            with Image.open(full_path) as img:
                return {"width": img.width, "height": img.height, "format": img.format}
        except Exception as e:
            logger.warning(f"Could not get dimensions for {file_path}: {str(e)}")
            return {"width": 0, "height": 0, "format": "unknown"}

    @staticmethod
    def _generate_contracted_url(file_path: str) -> str:
        """
        Generate contracted URL for frontend consumption
        Format: /media/products/images/{product_id}/{filename}
        """
        if settings.DEBUG:
            # In development, use Django's media serving
            return f"{settings.MEDIA_URL}{file_path}"
        else:
            # In production, you might want to use CDN or different domain
            base_url = getattr(settings, "MEDIA_BASE_URL", settings.MEDIA_URL)
            return f"{base_url}{file_path}"

    @staticmethod
    def delete_image_file(image_url: str) -> bool:
        """Delete image file from storage"""
        try:
            # Extract file path from URL
            if image_url.startswith(settings.MEDIA_URL):
                file_path = image_url.replace(settings.MEDIA_URL, "")
                if default_storage.exists(file_path):
                    default_storage.delete(file_path)
                    logger.info(f"Deleted image file: {file_path}")
                    return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete image file {image_url}: {str(e)}")
            return False

    @staticmethod
    def get_primary_image(product_id: uuid, product=None) -> Optional["ProductImage"]:
        """Get primary image with fallback to first image"""
        # If product instance is provided, use prefetched data
        if product and hasattr(product, "primary_images"):
            # Use prefetched primary images
            primary_images = getattr(product, "primary_images", [])
            if primary_images:
                return primary_images[0]

            # Fallback to all active images if they're prefetched
            all_images = getattr(product, "all_active_images", [])
            if all_images:
                return all_images[0]

        # If no prefetched data or no product instance, use cache
        if CacheManager.cache_exists("product_image", "primary", product_id=product_id):
            cache_key = CacheKeyManager.make_key(
                "product_image", "primary", product_id=product_id
            )
            try:
                cached_image = cache.get(cache_key)
                if cached_image is not None:
                    logger.info(f"Cache hit for primary image of product {product_id}")
                    return cached_image
            except Exception as e:
                logger.warning(
                    f"Cache retrieval failed for primary image of product {product_id}: {str(e)}"
                )

        cache_key = CacheKeyManager.make_key(
            "product_image", "primary", product_id=product_id
        )
        # If not cached, fetch from database
        logger.info(f"Fetching primary image for product {product_id} from database")

        try:
            # Try to get primary image first with minimal fields
            image = (
                ProductImage.objects.filter(
                    product_id=product_id, is_primary=True, is_active=True
                )
                .only("id", "product_id", "is_primary", "display_order")
                .first()
            )

            # Fallback to first available image
            if not image:
                image = (
                    ProductImage.objects.filter(product_id=product_id, is_active=True)
                    .only("id", "product_id", "is_primary", "display_order")
                    .order_by("display_order")
                    .first()
                )

            cache.set(cache_key, image, 3600)
            return image

        except ProductImage.DoesNotExist:
            return None

    @staticmethod
    def bulk_get_primary_images(
        product_ids: List[int], products=None
    ) -> Dict[int, "ProductImage"]:
        """Efficiently get primary images for multiple products"""
        start_time = time.time()
        # If products with prefetched data are provided, use them
        if products:
            result = {}
            for product in products:
                if hasattr(product, "primary_images") and product.primary_images:
                    result[product.id] = product.primary_images[0]
                elif (
                    hasattr(product, "all_active_images") and product.all_active_images
                ):
                    result[product.id] = product.all_active_images[0]

            # Only process uncached products that weren't in prefetched data
            uncached_product_ids = [pid for pid in product_ids if pid not in result]
            if not uncached_product_ids:
                return result
        else:
            result = {}
            uncached_product_ids = product_ids

        # For products without prefetched data, use cache
        cache_keys = {
            pid: CacheKeyManager.make_key("product_image", "primary", product_id=pid)
            for pid in uncached_product_ids
        }

        cached_results = cache.get_many(cache_keys.values())

        # Process cached results
        for product_id, cache_key in cache_keys.items():
            if cache_key in cached_results:
                result[product_id] = cached_results[cache_key]
            else:
                uncached_product_ids.append(product_id)

        # Fetch uncached images with minimal fields
        if uncached_product_ids:
            # Optimized query for primary images
            primary_images = (
                ProductImage.objects.filter(
                    product_id__in=uncached_product_ids, is_primary=True, is_active=True
                )
                .only("id", "image", "product_id", "is_primary", "display_order")
                .select_related("product")
            )

            primary_dict = {img.product_id: img for img in primary_images}

            # Get fallback images for products without primary
            missing_primary = [
                pid for pid in uncached_product_ids if pid not in primary_dict
            ]
            if missing_primary:
                fallback_images = (
                    ProductImage.objects.filter(
                        product_id__in=missing_primary, is_active=True
                    )
                    .only("id", "image", "product_id", "is_primary", "display_order")
                    .select_related("product")
                    .order_by("product_id", "display_order")
                    .distinct("product_id")
                )

                for img in fallback_images:
                    primary_dict[img.product_id] = img

            # Cache and add to result
            cache_data = {}
            for product_id in uncached_product_ids:
                image = primary_dict.get(product_id)
                result[product_id] = image
                cache_data[cache_keys[product_id]] = image

            cache.set_many(cache_data, 3600)

            duration = (time.time() - start_time) * 1000
            logger.info(
                f"Bulk fetched primary images for {len(uncached_product_ids)} products in {duration:.2f}ms"
            )

        return result

    @staticmethod
    @transaction.atomic
    def create_image_with_upload(
        product_id: int, uploaded_file, image_data: Dict, created_by_user: bool = True
    ) -> Dict:
        """Create image with file upload and database record"""
        start_time = time.time()

        try:
            # Upload file first
            upload_result = ProductImageService.upload_image(
                uploaded_file, product_id, image_data.get("variant_name")
            )

            if not upload_result["success"]:
                return upload_result

            # Validate variant if provided
            variant = None
            if image_data.get("variant_name"):
                variant = ProductImageVariant.objects.filter(
                    name=image_data["variant_name"], is_active=True
                ).first()

                if not variant:
                    # Clean up uploaded file
                    ProductImageService.delete_image_file(upload_result["image_url"])
                    raise ValueError(
                        f"Invalid variant: {image_data.get('variant_name')}"
                    )

            # Create database record
            image = ProductImage.objects.create(
                product_id=product_id,
                image_url=upload_result["image_url"],
                alt_text=image_data.get("alt_text", ""),
                is_primary=image_data.get("is_primary", False),
                display_order=image_data.get("display_order", 0),
                variant=variant,
                created_by_user=created_by_user,
                file_path=upload_result["file_path"],
                file_size=upload_result["file_size"],
                width=upload_result["dimensions"]["width"],
                height=upload_result["dimensions"]["height"],
            )

            # Handle primary image logic
            if image.is_primary:
                ProductImageService._ensure_single_primary(product_id, image.id)

            product = image.product
            # Invalidate cache
            CacheManager.invalidate_key("product_image", "list", product_id=product_id)
            CacheManager.invalidate_key(
                "product_image", "primary", product_id=product_id
            )
            from apps.products.product_base.services.product_detail_service import (
                ProductDetailService,
            )

            ProductListService.invalidate_product_list_caches()
            ProductDetailService.invalidate_product_cache(product.short_code)

            duration = (time.time() - start_time) * 1000
            logger.info(f"Created image with upload in {duration:.2f}ms")

            return {
                "success": True,
                "image": image,
                "uploaded_file_info": upload_result,
            }

        except Exception as e:
            logger.error(f"Failed to create image with upload: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def _ensure_single_primary(product_id: int, exclude_image_id: int = None):
        """Ensure only one primary image per product"""
        query = ProductImage.objects.filter(product_id=product_id, is_primary=True)
        if exclude_image_id:
            query = query.exclude(id=exclude_image_id)

        query.update(is_primary=False)

    @staticmethod
    def get_images_by_variant(product_id: int) -> Dict[str, List["ProductImage"]]:
        """Get images grouped by variant"""
        if CacheManager.cache_exists(
            "product_image", "variants", product_id=product_id
        ):
            cache_key = CacheKeyManager.make_key(
                "product_image", "variants", product_id=product_id
            )
            try:
                cached_variants = cache.get(cache_key)
                if cached_variants is not None:
                    return cached_variants
            except Exception as e:
                logger.warning(
                    f"Cache retrieval failed for product {product_id} variants: {str(e)}"
                )
        cache_key = CacheKeyManager.make_key(
            "product_image", "variants", product_id=product_id
        )
        logger.info(
            f"Fetching images by variant for product {product_id} from database"
        )

        images = (
            ProductImage.objects.filter(product_id=product_id, is_active=True)
            .select_related("variant")
            .order_by("variant__name", "display_order")
        )

        variants = {}
        for image in images:
            variant_name = image.variant.name if image.variant else "default"
            if variant_name not in variants:
                variants[variant_name] = []
            variants[variant_name].append(image)

        cache.set(cache_key, variants, 1800)  # 30 minutes
        return variants
