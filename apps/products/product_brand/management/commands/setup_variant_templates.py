from django.core.management.base import BaseCommand
from apps.products.product_brand.models import BrandVariantTemplate


class Command(BaseCommand):
    help = "Setup default variant templates"

    def handle(self, *args, **options):
        templates = [
            {
                "name": "Spanish (Spain)",
                "language_code": "es",
                "region_code": "ES",
                "auto_generate_for_brands": True,
                "brand_criteria": {"min_products": 5},
                "name_translations": {
                    "apple": "Apple",  # Brand names usually stay the same
                    "coca-cola": "Coca-Cola",
                },
                "default_settings": {"description": ""},  # Will use parent description
            },
            {
                "name": "French (France)",
                "language_code": "fr",
                "region_code": "FR",
                "auto_generate_for_brands": True,
                "brand_criteria": {"min_products": 5},
                "name_translations": {},
                "default_settings": {},
            },
            # Add more templates as needed
        ]

        for template_data in templates:
            template, created = BrandVariantTemplate.objects.get_or_create(
                name=template_data["name"], defaults=template_data
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Created template: {template.name}")
                )
            else:
                self.stdout.write(f"Template already exists: {template.name}")
