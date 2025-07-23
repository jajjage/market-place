import os
import uuid
from celery import shared_task
from django.core.files import File as DjangoFile
from django.core.files.storage import default_storage

from apps.core.tasks import BaseTaskWithRetry
from .services import ProductImageService


@shared_task(bind=True, base=BaseTaskWithRetry)
def upload_product_image_task(
    self,
    product_id: uuid.UUID = None,
    file_path: str = None,
    alt_text: str = "",
    is_primary: bool = False,
    display_order: int = 0,
    variant_name: str = None,
    created_by_user=False,
):
    """
    Celery task to upload a single product image.
    If `file_path` is absolute, open it directly; otherwise use default_storage.
    """
    # 1. Open the file, choosing the right backend
    if os.path.isabs(file_path):
        f = open(file_path, "rb")
    else:
        f = default_storage.open(file_path, "rb")

    # 2. Wrap in DjangoFile so that DRF’s ImageField sees a .name attribute
    django_file = DjangoFile(f, name=os.path.basename(file_path))

    try:
        # 3. Delegate to your service
        result = ProductImageService.create_image_with_upload(
            product_id=product_id,
            uploaded_file=django_file,
            image_data={
                "alt_text": alt_text,
                "is_primary": is_primary,
                "display_order": display_order,
                "variant_name": variant_name,
            },
            created_by_user=created_by_user,
        )

        # 4. Cleanup & error handling
        # (optional) delete the temp file if you saved it under MEDIA
        if not os.path.isabs(file_path):
            default_storage.delete(file_path)

        if not result["success"]:
            # Raise to let Celery mark this task as failed
            raise RuntimeError(f"Upload failed: {result['error']}")

        return result["image"].id

    finally:
        # always close the file handle
        f.close()
