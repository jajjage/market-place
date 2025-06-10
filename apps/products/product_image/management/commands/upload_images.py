import json
import os

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.contrib.auth import get_user_model

from apps.products.product_image.tasks import upload_product_image_task

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Bulk-upload product images from a JSON manifest. "
        "Each entry needs 'product_id', 'file_path', plus any metadata."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--manifest",
            "-m",
            required=True,
            help="Path to JSON file listing images and metadata",
        )
        parser.add_argument(
            "--user_email",
            "-u",
            type=str,
            default="admin@example.com",
            help="Email to act as (for created_by_user flag)",
        )

    def handle(self, *args, **options):
        manifest_path = options["manifest"]
        email = options["user_email"]

        # 1. Resolve user
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise CommandError(f"User '{email}' not found.")

        # 2. Load manifest
        if not os.path.exists(manifest_path):
            raise CommandError(f"Manifest file not found: {manifest_path}")
        with open(manifest_path, "r") as fp:
            entries = json.load(fp)

        total = len(entries)
        self.stdout.write(self.style.NOTICE(f"Processing {total} entries…"))

        queued = 0
        errors = []

        for idx, entry in enumerate(entries, start=1):
            product_id = entry.get("product_id")
            file_path = entry.get("file_path")

            if not product_id or not file_path:
                errors.append(f"[{idx}] Missing product_id or file_path")
                continue

            # Build absolute path
            abs_path = (
                file_path
                if os.path.isabs(file_path)
                else os.path.join(settings.BASE_DIR, file_path)
            )
            if not os.path.isfile(abs_path):
                errors.append(f"[{idx}] File not found: {abs_path}")
                continue

            # Gather metadata
            task_kwargs = {
                "product_id": product_id,
                "file_path": abs_path,
                "alt_text": entry.get("alt_text", ""),
                "is_primary": bool(entry.get("is_primary", False)),
                "display_order": int(entry.get("display_order", 0)),
                "variant_name": entry.get("variant_name"),
                "created_by_user": not user.is_staff,
            }

            try:
                # 3. Enqueue Celery task
                async_result = upload_product_image_task.delay(**task_kwargs)
                queued += 1
                self.stdout.write(f"  ✉ [{idx}] queued task {async_result.id}")
            except Exception as e:
                errors.append(f"[{idx}] Task enqueue failed: {e}")

        # 4. Summary
        self.stdout.write(
            self.style.SUCCESS(f"Done! {queued} tasks queued, {len(errors)} errors.")
        )
        if errors:
            for err in errors:
                self.stdout.write(self.style.ERROR(err))
            raise CommandError("Some entries failed; see errors above.")
