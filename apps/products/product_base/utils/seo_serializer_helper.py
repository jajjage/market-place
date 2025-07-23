from typing import Iterable
import logging

from django.conf import settings
from apps.core.serializers import BreadcrumbSerializer
from apps.core.utils.breadcrumbs import BreadcrumbService
from apps.products.product_base.utils.utils import (
    clean_description,
    safe_get_variant_options,
)
from apps.products.product_detail.models import ProductDetail

logger = logging.getLogger(__name__)


def get_breadcrumbs(obj) -> list[dict]:
    service = BreadcrumbService()
    breadcrumb_data = service.for_product(obj, include_brand=True)
    return BreadcrumbSerializer(breadcrumb_data, many=True).data


def get_additional_properties(details):
    """
    Accepts:
    - A QuerySet or list of ProductDetail instances
    - A list of dicts with keys 'label' & 'formatted_value' (or 'value')
    Returns:
    - A list of schema.org PropertyValue dicts
    """
    # Guard: nothing to do
    if not details:
        return []

    # If it’s a QuerySet, cast to list
    if hasattr(details, "all") and callable(details.all):
        details = list(details.all())

    # If it’s some other iterable (e.g. manager), cast to list too
    if not isinstance(details, list) and isinstance(details, Iterable):
        details = list(details)

    properties = []
    for detail in details:
        # Case A: dict from serializer
        if isinstance(detail, dict):
            label = detail.get("label")
            value = detail.get("formatted_value") or detail.get("value")
            logger.info(f"it is dict: {detail}")
        # Case B: model instance
        elif isinstance(detail, ProductDetail):
            label = detail.label
            # if you’ve added a property or method for formatted_value, use that:
            value = getattr(detail, "formatted_value", None) or detail.value
        else:
            continue  # skip anything else

        if label and value:
            properties.append(
                {
                    "@type": "PropertyValue",
                    "name": label,
                    "value": value,
                }
            )

    return properties


def get_variant_info(variants):
    """Extract variant information for structured data - OPTIMIZED VERSION"""
    if not variants:
        return {}

    variant_info = {}
    colors = set()
    sizes = set()
    styles = set()

    for variant in variants:
        # Use the optimized function that respects prefetched data
        options_list = safe_get_variant_options(variant)

        for option in options_list:
            if isinstance(option, dict):
                option_type = option.get("type", "").lower()
                option_value = option.get("value", "")

                if option_type == "color" and option_value:
                    colors.add(option_value)
                elif option_type == "size" and option_value:
                    sizes.add(option_value)
                elif option_type == "style" and option_value:
                    styles.add(option_value)

    # Add to structured data if found
    if colors:
        variant_info["color"] = list(colors)[0] if len(colors) == 1 else list(colors)
    if sizes:
        variant_info["size"] = list(sizes)[0] if len(sizes) == 1 else list(sizes)
    if styles:
        variant_info["model"] = list(styles)[0] if len(styles) == 1 else list(styles)

    return variant_info


def get_pricing_info(obj):
    """Get comprehensive pricing information"""
    base_url = settings.FRONTEND_BASE_URL

    # Check if we have variants with different prices
    variant_prices = []
    if hasattr(obj, "variants") and obj.variants:
        variants = getattr(obj, "prefetched_variants", obj.variants.all())
        for variant in variants:
            if isinstance(variant, dict) and "price" in variant and variant["price"]:
                try:
                    price = float(variant["price"])
                    if price > 0:
                        variant_prices.append(price)
                except (ValueError, TypeError):
                    continue

    # Use main price or variant price range
    main_price = obj.price if obj.price and float(obj.price) > 0 else None

    if not main_price and not variant_prices:
        return None

    # Determine final price to display
    if variant_prices:
        min_price = min(variant_prices)
        max_price = max(variant_prices)
        display_price = (
            f"{min_price:.2f}"
            if min_price == max_price
            else f"{min_price:.2f}-{max_price:.2f}"
        )
    else:
        display_price = str(main_price)

    return {
        "@type": "Offer",
        "price": display_price,
        "priceCurrency": getattr(obj, "currency", "USD"),
        "availability": (
            "https://schema.org/InStock"
            if getattr(obj, "is_active", False)
            else "https://schema.org/OutOfStock"
        ),
        "url": f"{base_url}/products/{obj.slug}",
        "seller": {"@type": "Organization", "name": "TrustLock"},
    }


def get_breadcrumb_data(breadcrumbs, base_url):
    """Generate breadcrumb structured data"""
    if not breadcrumbs:
        return None

    breadcrumb_list = []
    for i, breadcrumb in enumerate(breadcrumbs):
        if isinstance(breadcrumb, dict) and breadcrumb.get("name"):
            href = breadcrumb.get("href")
            if href:  # Only include items with URLs
                breadcrumb_list.append(
                    {
                        "@type": "ListItem",
                        "position": i + 1,
                        "name": breadcrumb["name"],
                        "item": f"{base_url}{href}",
                    }
                )

    return (
        {"@type": "BreadcrumbList", "itemListElement": breadcrumb_list}
        if breadcrumb_list
        else None
    )


def get_condition_text(condition):
    """Convert condition code to schema.org condition"""
    if not condition:
        return "https://schema.org/UsedCondition"

    condition_map = {
        "new": "NewCondition",
        "open_box": "OpenBoxCondition",
        "used_good": "UsedCondition",
        "refurbished": "RefurbishedCondition",
        "damaged": "DamagedCondition",
    }
    return f"https://schema.org/{condition_map.get(condition.lower(), 'UsedCondition')}"


def get_product_images(obj):
    """
    Return up to 5 image URLs:
    - First up to 3 from the Product.images manager.
    - If none, up to 2 from the first variant that has images.
    """
    urls = []

    # 1) Main product images (up to 3)
    images = getattr(obj, "prefetched_images", obj.images.all())
    for img in images[:3]:
        # assume each Image model has a 'file' or 'url' attribute
        path = getattr(img, "url", None) or getattr(img, "file", None)
        if path:
            urls.append(f"{settings.MEDIA_URL}{path}")

    # 2) Fallback to variant images (up to 2) if no main images
    if not urls:
        variants = getattr(obj, "prefetched_variants", [])
        for variant in variants:
            # Get variant images through the prefetched data
            variant_images = getattr(variant, "prefetched_variant_images", [])

            if not variant_images:
                continue

            # Process up to 2 images from this variant
            for img in variant_images[:2]:
                path = getattr(img, "image", None)
                if path:
                    urls.append(f"{settings.MEDIA_URL}{path}")

            # Break after processing first variant with images
            if urls:
                break
    return urls[:5]


def get_structured_data(obj):
    """Generate JSON-LD structured data with variants and details"""
    base_url = settings.FRONTEND_BASE_URL

    structured_data = {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": obj.title,
        "description": clean_description(obj.description),
        "brand": {
            "@type": "Brand",
            "name": obj.brand.name,
            "url": f"{base_url}/brands/{obj.brand.slug}",
        },
        "category": obj.category.name,
        "condition": get_condition_text(obj.condition.name),
        "url": f"{base_url}/products/{obj.slug}",
        "image": get_product_images(obj),
        "sku": obj.short_code,
    }

    # Add details as additional properties if available
    details = getattr(obj, "prefetched_details", [])
    if details:
        additional_properties = get_additional_properties(details)
        logger.info(
            f"Adding product details to structured data for {additional_properties}"
        )
        if additional_properties:
            structured_data["additionalProperty"] = additional_properties

    # Add variant information if available
    variants = getattr(obj, "prefetched_variants", [])
    logger.info(f"Found {len(variants)} variants for structured data: {variants}")
    if variants:
        variant_info = get_variant_info(variants)
        if variant_info:
            structured_data.update(variant_info)

    # Add pricing info
    pricing_info = get_pricing_info(obj)
    if pricing_info:
        structured_data["offers"] = pricing_info

    # Add ratings if available
    if (
        hasattr(obj, "user_rating")
        and obj.user_rating
        and obj.user_rating.get("average")
    ):
        logger.info(f"Adding user_rating to structured data for {obj.user_rating}")
        structured_data["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": str(obj.user_rating["average"]),
            "reviewCount": str(obj.user_rating["total"]),
        }

    # Add breadcrumbs if available
    breadcrumbs = get_breadcrumbs(obj)
    if breadcrumbs:
        breadcrumb_data = get_breadcrumb_data(breadcrumbs, base_url)
        if breadcrumb_data:
            structured_data["breadcrumb"] = breadcrumb_data

    return structured_data
