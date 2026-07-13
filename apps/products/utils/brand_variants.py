from typing import Dict, Any
import logging

from ..models import Brand, BrandVariant, BrandVariantTemplate


logger = logging.getLogger(__name__)


def brand_meets_criteria(brand: Brand, criteria: Dict[str, Any]) -> bool:
    """
    Check if a brand meets the template criteria

    Args:
        brand: Brand instance
        criteria: Template criteria dictionary

    Returns:
        bool: True if brand meets criteria
    """
    if not criteria:
        return True

    # Check country of origin
    if "country_of_origin" in criteria:
        allowed_countries = criteria["country_of_origin"]
        if isinstance(allowed_countries, list):
            if brand.country_of_origin not in allowed_countries:
                return False
        elif brand.country_of_origin != allowed_countries:
            return False

    # Check minimum founded year
    if "min_founded_year" in criteria:
        if brand.founded_year and brand.founded_year < criteria["min_founded_year"]:
            return False

    # Check if brand is verified (if required)
    if criteria.get("require_verified", False):
        if not brand.is_verified:
            return False

    # Check if brand is featured (if required)
    if criteria.get("require_featured", False):
        if not brand.is_featured:
            return False

    # Check minimum products count (if you have products relationship)
    if "min_products" in criteria:
        # Assuming you have a products relationship
        # product_count = brand.products.filter(is_active=True).count()
        # if product_count < criteria['min_products']:
        #     return False
        pass

    return True


def create_variant_from_template(
    brand: Brand, template: BrandVariantTemplate
) -> BrandVariant:
    """
    Create a brand variant from a template

    Args:
        brand: Brand instance
        template: BrandVariantTemplate instance

    Returns:
        BrandVariant: Created variant
    """
    # Generate localized name using template translations
    variant_name = generate_localized_name(brand, template)

    # Create variant data
    variant_data = {
        "brand": brand,
        "template": template,
        "name": variant_name,
        "language_code": template.language_code,
        "region_code": template.region_code,
        "description": generate_localized_description(brand, template),
        "is_auto_generated": True,
        "is_active": True,
        "created_by": None,  # System generated
    }

    # Apply default settings from template
    if template.default_settings:
        # You can extend this based on what settings you want to apply
        pass

    variant = BrandVariant.objects.create(**variant_data)

    logger.info(
        f"Created variant {variant.id} for brand {brand.name} using template {template.name}"
    )

    return variant


def generate_localized_name(brand: Brand, template: BrandVariantTemplate) -> str:
    """
    Generate localized name for the variant

    Args:
        brand: Brand instance
        template: BrandVariantTemplate instance

    Returns:
        str: Localized name
    """
    base_name = brand.name

    # Apply translations from template
    translations = template.name_translations

    if "Default Suffix" in translations:
        suffix = translations["Default Suffix"]
        # Only add suffix if not already present
        if not base_name.endswith(suffix):
            base_name = f"{base_name} {suffix}"

    if "Prefix" in translations:
        prefix = translations["Prefix"]
        if not base_name.startswith(prefix):
            base_name = f"{prefix} {base_name}"

    # Apply name replacements
    if "replacements" in translations:
        for old_text, new_text in translations["replacements"].items():
            base_name = base_name.replace(old_text, new_text)

    return base_name


def generate_localized_description(brand: Brand, template: BrandVariantTemplate) -> str:
    """
    Generate localized description for the variant

    Args:
        brand: Brand instance
        template: BrandVariantTemplate instance

    Returns:
        str: Localized description
    """
    base_description = brand.description

    # Apply localization based on template settings
    if template.default_settings.get("description_template"):
        template_desc = template.default_settings["description_template"]
        # Replace placeholders
        localized_desc = template_desc.format(
            brand_name=brand.name,
            country=brand.country_of_origin,
            region=template.region_code,
        )
        return localized_desc

    return base_description
