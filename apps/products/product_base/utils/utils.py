import re
import logging

logger = logging.getLogger(__name__)


def clean_description(description):
    """Clean description from markdown and formatting for JSON-LD"""
    if not description:
        return ""

    # Remove markdown formatting
    clean_desc = re.sub(r"\*\*(.*?)\*\*", r"\1", description)

    # Remove array formatting like ['* text', '* text']
    clean_desc = re.sub(r"\[\'?\*\s*([^\']+)\'?,?\s*\]", "", clean_desc)
    clean_desc = re.sub(r"\[\'([^\']+)\',?\s*\'([^\']+)\'.*?\]", "", clean_desc)

    # Remove bullet points and extra whitespace
    clean_desc = re.sub(r"\n\s*\[\*.*?\]", "", clean_desc, flags=re.DOTALL)
    clean_desc = re.sub(r"\*\s+", "", clean_desc)
    clean_desc = re.sub(r"\n+", " ", clean_desc)
    clean_desc = clean_desc.strip()

    # Limit to reasonable length for structured data
    return clean_desc[:700] + "..." if len(clean_desc) > 700 else clean_desc


def safe_get_variant_options(variant):
    """
    Safely extract options from a variant, ALWAYS prioritizing prefetched data.
    """
    from apps.products.product_variant.models import ProductVariant

    if isinstance(variant, ProductVariant):
        # ALWAYS check for prefetched data first
        if hasattr(variant, "prefetched_variant_options"):
            return [
                {"type": opt.variant_type.name, "value": opt.value}
                for opt in variant.prefetched_variant_options
            ]

        # Only fall back to manager if absolutely no prefetched data
        # This should rarely happen if prefetching is set up correctly
        if hasattr(variant, "options"):
            logger.warning(f"Using non-prefetched options for variant {variant.id}")
            return [
                {"type": opt.variant_type.name, "value": opt.value}
                for opt in variant.options.select_related("variant_type")
            ]

    elif isinstance(variant, dict):
        return variant.get("options", [])

    return []


def generate_seo_title(obj):

    base = f"{obj.title} | {obj.brand.name}"

    # Safe variant iteration with proper error handling
    try:
        variants = getattr(obj, "prefetched_variants", obj.variants.all())
        for v in variants:
            options = safe_get_variant_options(v)
            logger.info(f"Processing variant: {options} for SEO title")

            # Find color option
            color = None
            for opt in options:
                if isinstance(opt, dict) and opt.get("type", "").lower() == "color":
                    color = opt.get("value")
                    break

            if color and len(base) + len(color) + 3 < 60:
                return f"{obj.title} {color} | {obj.brand.name}"[:60]
    except Exception as e:
        # Log it and re‑raise so you actually see the traceback
        logger.exception("generate_meta_description failed")
        raise

    return base[:60]


def generate_meta_description(obj):
    parts = [f"Shop authentic {obj.brand.name} {obj.title.lower()}"]

    # Safe variant processing
    try:
        variants = getattr(obj, "prefetched_variants", obj.variants.all())
        for v in variants:
            options = safe_get_variant_options(v)
            logger.info(f"Processing variant: {options} for meta description")

            color = None
            size = None

            for opt in options:
                if isinstance(opt, dict):
                    opt_type = opt.get("type", "").lower()
                    opt_value = opt.get("value", "")

                    if opt_type == "color" and opt_value:
                        color = opt_value
                    elif opt_type == "size" and opt_value:
                        size = opt_value

            if color:
                parts.append(f"in {color.lower()}")
            if size:
                parts.append(f"size {size.lower()}")
            break  # Only use first variant
    except Exception as e:
        # Log it and re‑raise so you actually see the traceback
        logger.exception("generate_meta_description failed")
        raise

    # Material detail - use try/catch for safe access
    try:
        details = getattr(obj, "prefetched_details", [])
        for d in details:
            if d.is_active:
                if "material" in d.label.lower():
                    mat = getattr(d, "formatted_value", d.value) or ""
                    if mat and len(mat) < 20:
                        parts.append(f"made from {mat.lower()}")
                    break
    except Exception as e:
        # Log it and re‑raise so you actually see the traceback
        logger.exception("generate_meta_description failed")
        raise

    # Category & condition
    if obj.category:
        parts.append(obj.category.name)
    if obj.condition:
        parts.append(f"in {obj.condition.name.replace('_', ' ')} condition")

    parts.append("Secure escrow payment and authenticity guaranteed.")
    return ". ".join(parts)[:160]


def generate_enhanced_keywords(obj):
    """
    Generates a combined list of keywords from prefetched meta
    and dynamic attributes.
    """
    # Initialize the set at the beginning
    kw = set()

    # Add keywords from meta if they exist
    meta = getattr(obj, "prefetched_meta", None)
    if meta and hasattr(meta, "seo_keywords") and isinstance(meta.seo_keywords, list):
        # Use update() to add the meta keywords to the set
        meta_keywords = [k.lower() for k in meta.seo_keywords if isinstance(k, str)]
        kw.update(meta_keywords)

    # Now, proceed with generating the rest of the keywords
    brand = obj.brand.name.lower()
    title = obj.title.lower()
    cat = obj.category.name.lower() if obj.category else ""

    base = [
        f"{brand} {title}",
        f"authentic {brand}",
        f"{brand} {cat}",
        f"pre-owned {brand}",
        f"{obj.condition or 'used'} {brand}",
        f"luxury {cat}",
        f"{brand} for sale",
    ]
    kw.update(base)

    # Safe variant processing
    try:
        variants = getattr(obj, "prefetched_variants", obj.variants.all())
        for v in variants:
            options = safe_get_variant_options(v)
            for opt in options:
                if isinstance(opt, dict):
                    val = opt.get("value", "").lower()
                    typ = opt.get("type", "").lower()
                    if val:
                        kw.add(f"{val} {brand} {title.split()[0]}")
                        kw.add(f"{brand} {val} {typ}")
                        kw.add(f"{val} {cat}")
    except Exception as e:
        # Log it and re‑raise so you actually see the traceback
        logger.exception("generate_meta_description failed")
        raise
    # Safe material details processing
    try:
        details = getattr(obj, "prefetched_details", [])
        for d in details:
            if d.is_active:
                lbl = d.label.lower()
                val = (getattr(d, "formatted_value", d.value) or "").lower()
                if "material" in lbl and val:
                    kw.add(f"{val} {brand}")
                    kw.add(f"{brand} {val} {cat}")
    except Exception as e:
        # Log it and re‑raise so you actually see the traceback
        logger.exception("generate_meta_description failed")
        raise

    # Title word combos
    words = [w for w in title.split() if len(w) > 3][:3]
    for w in words:
        kw.add(f"{w} {brand}")
        kw.add(f"{brand} {w}")

    # The final list will contain both meta and generated keywords
    return list(kw)
