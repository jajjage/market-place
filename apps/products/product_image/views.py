# views.py with proper caching and rate limiting
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from apps.core.views import BaseViewSet
from apps.core.utils.cache_manager import CacheManager
from apps.products.product_image.models import ProductImage
from apps.products.product_image.serializers import (
    ProductImageBulkUploadSerializer,
    ProductImageSerializer,
    ProductImageUploadSerializer,
)
from apps.products.product_image.services import ProductImageService
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers

from apps.products.product_image.utils.rate_limiting import (
    ImageBulkTUploadThrottle,
    ImageUploadThrottle,
)


class ProductImageViewSet(BaseViewSet):
    serializer_class = ProductImageSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        product_id = self.request.query_params.get("product_id")
        if product_id:
            return ProductImageService.get_product_images(product_id)
        return ProductImage.objects.none()

    def get_throttles(self):
        # Use different throttles for bulk_upload and upload_image actions
        if self.action == "bulk_upload":
            throttle_classes = [ImageBulkTUploadThrottle]
        elif self.action == "upload_image":
            throttle_classes = [ImageUploadThrottle]
        else:
            throttle_classes = []
        return [throttle() for throttle in throttle_classes]

    @method_decorator(cache_page(60 * 15))  # 15 minutes
    @method_decorator(vary_on_headers("Authorization"))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=["post"])
    def upload_image(self, request):
        """Upload single image with file"""
        product_id = request.data.get("product_id")
        if not product_id:
            return Response({"error": "product_id required"}, status=400)

        serializer = ProductImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Extract uploaded file and other data
        uploaded_file = serializer.validated_data.pop("image")
        image_data = serializer.validated_data

        # Create image with upload
        result = ProductImageService.create_image_with_upload(
            product_id=int(product_id),
            uploaded_file=uploaded_file,
            image_data=image_data,
            created_by_user=not request.user.is_staff,
        )

        if result["success"]:
            response_serializer = ProductImageSerializer(result["image"])
            return Response(
                {
                    "image": response_serializer.data,
                    "upload_info": {
                        "file_size_mb": round(
                            result["uploaded_file_info"]["file_size"] / (1024 * 1024), 2
                        ),
                        "dimensions": result["uploaded_file_info"]["dimensions"],
                        "filename": result["uploaded_file_info"]["filename"],
                    },
                },
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response({"error": result["error"]}, status=400)

    @action(detail=False, methods=["post"])
    def bulk_upload(self, request):
        """Bulk upload images with files"""
        product_id = request.data.get("product_id")
        if not product_id:
            return Response({"error": "product_id required"}, status=400)

        # Handle multiple file uploads
        uploaded_files = request.FILES.getlist("images")
        alt_texts = request.data.getlist("alt_texts", [])
        variant_names = request.data.getlist("variant_names", [])

        if not uploaded_files:
            return Response({"error": "No images provided"}, status=400)

        if len(uploaded_files) > 5:
            return Response({"error": "Maximum 5 images per bulk upload"}, status=400)

        created_images = []
        errors = []

        for i, uploaded_file in enumerate(uploaded_files):
            image_data = {
                "alt_text": alt_texts[i] if i < len(alt_texts) else "",
                "variant_name": variant_names[i] if i < len(variant_names) else "",
                "display_order": i,
                "is_primary": i == 0
                and len(created_images) == 0,  # First image as primary if none exists
            }

            result = ProductImageService.create_image_with_upload(
                product_id=int(product_id),
                uploaded_file=uploaded_file,
                image_data=image_data,
                created_by_user=not request.user.is_staff,
            )

            if result["success"]:
                created_images.append(result["image"])
            else:
                errors.append({"file": uploaded_file.name, "error": result["error"]})

        response_serializer = ProductImageSerializer(created_images, many=True)
        response_data = {
            "created_images": response_serializer.data,
            "created_count": len(created_images),
            "total_attempted": len(uploaded_files),
        }

        if errors:
            response_data["errors"] = errors

        return Response(
            response_data, status=status.HTTP_201_CREATED if created_images else 400
        )

    @action(detail=False, methods=["get"])
    @method_decorator(cache_page(60 * 30))  # 30 minutes
    def primary(self, request):
        """Get primary image for a product"""
        product_id = request.query_params.get("product_id")
        if not product_id:
            return Response({"error": "product_id required"}, status=400)

        image = ProductImageService.get_primary_image(int(product_id))
        if image:
            serializer = self.get_serializer(image)
            return Response(serializer.data)
        return Response({"error": "No image found"}, status=404)

    @action(detail=False, methods=["get"])
    @method_decorator(cache_page(60 * 15))
    def variants(self, request):
        """Get images grouped by variant"""
        product_id = request.query_params.get("product_id")
        if not product_id:
            return Response({"error": "product_id required"}, status=400)

        variants = ProductImageService.get_image_variants(int(product_id))
        serialized_variants = {}

        for variant_name, images in variants.items():
            serialized_variants[variant_name] = self.get_serializer(
                images, many=True
            ).data

        return Response(serialized_variants)

    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        """Bulk create images (legacy endpoint for URL-based images)"""
        serializer = ProductImageBulkUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_id = request.data.get("product_id")
        if not product_id:
            return Response({"error": "product_id required"}, status=400)

        created_images = []
        for image_data in serializer.validated_data["images"]:
            image = ProductImageService.create_image_variant(
                product_id=product_id,
                variant_data=image_data,
                created_by_user=not request.user.is_staff,
            )
            created_images.append(image)

        response_serializer = self.get_serializer(created_images, many=True)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        """Override destroy to handle file deletion"""
        instance = self.get_object()

        # Delete associated file
        if instance.file_path:
            ProductImageService.delete_image_file(instance.image_url)

        # Invalidate cache
        CacheManager.invalidate("product_image", product_id=instance.product_id)

        return super().destroy(request, *args, **kwargs)
