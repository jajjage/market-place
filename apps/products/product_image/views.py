# views.py with proper caching and rate limiting
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from apps.core.views import BaseViewSet
from apps.core.utils.cache_manager import CacheManager
from apps.products.product_image.models import ProductImage, ProductImageVariant
from apps.products.product_image.permissions import IsAdminOrStaff
from apps.products.product_image.serializers import (
    ProductImageBulkUploadSerializer,
    ProductImageSerializer,
    ProductImageUploadSerializer,
    ProductImageVariantSerializer,
)
from apps.products.product_image.services import ProductImageService

from apps.products.product_image.tasks import upload_product_image_task
from apps.products.product_image.utils.rate_limiting import (
    ImageBulkUploadThrottle,
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
            throttle_classes = [ImageBulkUploadThrottle]
        elif self.action == "upload_image":
            throttle_classes = [ImageUploadThrottle]
        else:
            throttle_classes = []
        return [throttle() for throttle in throttle_classes]

    @action(detail=False, methods=["post"])
    def upload_image(self, request):
        serializer = ProductImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = request.FILES["image"]
        product_id = serializer.validated_data["product_id"]
        alt_text = serializer.validated_data.get("alt_text", "")
        is_primary = serializer.validated_data.get("is_primary", False)
        display_order = serializer.validated_data.get("display_order", 0)
        variant_name = serializer.validated_data.get("variant_name")

        # 1) Save the incoming file to a stable location your worker can access.
        #    Here we let Django’s default storage save it:
        from django.core.files.storage import default_storage

        path = default_storage.save(f"temp/uploads/{uploaded_file.name}", uploaded_file)

        # 2) Enqueue the task
        task = upload_product_image_task.delay(
            product_id=product_id,
            file_path=path,
            alt_text=alt_text,
            is_primary=is_primary,
            display_order=display_order,
            variant_name=variant_name,
            created_by_user=not request.user.is_staff,
        )

        # 3) Return immediately
        return self.success_response(
            data={"detail": "Upload queued", "task_id": task.id},
            status_code=status.HTTP_202_ACCEPTED,
        )

    @action(detail=False, methods=["post"])
    def bulk_upload(self, request):
        # validate product_id
        product_id = request.data.get("product_id")
        if not product_id:
            return Response({"error": "product_id required"}, 400)

        uploaded_files = request.FILES.getlist("images")
        if not uploaded_files:
            return Response({"error": "No images provided"}, 400)

        from django.core.files.storage import default_storage

        queued = []
        for i, uploaded_file in enumerate(uploaded_files):
            # persist file
            path = default_storage.save(
                f"temp/uploads/{uploaded_file.name}", uploaded_file
            )

            # metadata
            meta = {
                "alt_text": (
                    request.data.getlist("alt_texts", [])[i]
                    if i < len(request.data.getlist("alt_texts", []))
                    else ""
                ),
                "variant_name": (
                    request.data.getlist("variant_names", [])[i]
                    if i < len(request.data.getlist("variant_names", []))
                    else None
                ),
                "display_order": i,
                "is_primary": (i == 0),
            }

            # enqueue each
            task = upload_product_image_task.delay(
                product_id=product_id,
                file_path=path,
                **meta,
                created_by_user=not request.user.is_staff,
            )
            queued.append(task.id)

        return self.success_response(
            data={"detail": "Bulk upload queued", "task_ids": queued},
            status_code=status.HTTP_202_ACCEPTED,
        )

    @action(detail=False, methods=["get"])
    def primary(self, request):
        """Get primary image for a product"""
        product_id = request.query_params.get("product_id")
        if not product_id:
            return Response({"error": "product_id required"}, status=400)

        image = ProductImageService.get_primary_image(product_id)
        if image:
            serializer = self.get_serializer(image)
            return Response(serializer.data)
        return Response({"error": "No image found"}, status=404)

    @action(detail=False, methods=["get"])
    def variants(self, request):
        """Get images grouped by variant"""
        product_id = request.query_params.get("product_id")
        if not product_id:
            return Response({"error": "product_id required"}, status=400)

        variants = ProductImageService.get_images_by_variant(int(product_id))
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


class ProductImageVariantViewSet(BaseViewSet):
    queryset = ProductImageVariant.objects.all()
    serializer_class = ProductImageVariantSerializer
    permission_classes = [IsAdminOrStaff]

    def get_queryset(self):
        # Optionally filter by is_active
        is_active = self.request.query_params.get("is_active")
        queryset = super().get_queryset()
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by_admin=True)
