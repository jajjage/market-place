import re
from typing import Any, Dict, List, Tuple, Optional

# Define tone rules: (trigger words, tone label, min_price, max_price)
TONE_RULES: List[Tuple[List[str], str, Optional[float], Optional[float]]] = [
    (["organic", "eco", "sustainable"], "warm & eco‑conscious", None, None),
    (["professional", "technical", "industrial"], "professional", None, None),
    (["gaming", "console", "entertainment"], "enthusiastic", None, None),
    (["luxury", "premium", "exclusive"], "sophisticated", 500, None),
    (["kids", "children", "family"], "friendly", None, None),
    (["fitness", "workout", "gym"], "energetic", None, None),
    # Add more rules as needed
]


def build_corpus(product: Any, context_info: Dict[str, Any]) -> str:
    """
    Build a lowercase text blob from product attributes and context for analysis.

    Combines title, category, active details, variant options, and price into one string.

    Args:
        product: Django model instance with attributes 'title', 'product_details', 'variants'.
        context_info: Dictionary containing context keys 'category' and 'price'.

    Returns:
        A single string containing all text segments joined by spaces.
    """
    parts: List[str] = [
        product.title.lower(),
        context_info.get("category", "").lower(),
    ]

    # Append product details safely
    details_manager = getattr(product, "product_details", None)
    if hasattr(details_manager, "all"):
        for d in details_manager.all():
            parts.append(f"{d.label} {d.value}".lower())

    # Append variant options safely
    variants_manager = getattr(product, "variants", None)
    if hasattr(variants_manager, "all"):
        for v in variants_manager.all():
            opts_manager = getattr(v, "options", None)
            if hasattr(opts_manager, "all"):
                for o in opts_manager.all():
                    parts.append(f"{o.variant_type.name} {o.value}".lower())

    # Append price as text
    price = context_info.get("price")
    if price:
        parts.append(str(price))

    return " ".join(parts)


def extract_product_info_and_context(
    product: Any,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Extract structured product_info and context_info from a product instance.

    Gathers title, brand, category, condition, price, location, existing description features,
    product details, variants, and flags like authenticity or negotiability.

    Args:
        product: Django model instance with various related fields.

    Returns:
        A tuple of (product_info, context_info) dictionaries.
    """
    product_info: Dict[str, Any] = {}
    context_info: Dict[str, Any] = {}

    # Basic attributes
    product_info["title"] = product.title

    if getattr(product, "brand", None):
        product_info["brand"] = product.brand.name
        context_info["brand"] = product.brand.name

    if getattr(product, "category", None):
        product_info["category"] = product.category.name
        context_info["category"] = product.category.name

    if getattr(product, "condition", None):
        product_info["condition"] = product.condition.name
        context_info["condition"] = product.condition.name

    if getattr(product, "price", None) is not None:
        product_info["price"] = product.price
        context_info["price"] = product.price

    if getattr(product, "location", None):
        product_info["location"] = product.location
        context_info["location"] = product.location

    # Extract features from existing description
    if getattr(product, "description", None):
        desc_clean = re.sub(r"[^\w\s]", " ", product.description.lower())
        desc_words = desc_clean.split()
        feature_terms = [
            "wireless",
            "bluetooth",
            "rechargeable",
            "waterproof",
            "portable",
            "durable",
            "premium",
            "professional",
            "automatic",
            "manual",
            "digital",
            "analog",
            "smart",
            "advanced",
            "high-quality",
        ]
        features = [term for term in feature_terms if term in desc_words]
        if features:
            product_info["features"] = ", ".join(features)

    # Details
    details_qs = product.product_details.filter(is_active=True).order_by(
        "display_order"
    )
    if details_qs.exists():
        product_info["detail"] = "; ".join(
            f"{d.label}: {d.formatted_value}" for d in details_qs
        )

    # Variants
    variants_qs = product.variants.filter(is_active=True)
    product_info["variants"] = [
        {
            "sku": v.sku,
            "price": v.price,
            "options": [
                {"type": o.variant_type.name, "value": o.value, "slug": o.slug}
                for o in v.options.all()
            ],
        }
        for v in variants_qs
    ]

    # Flags
    if getattr(product, "authenticity_guaranteed", False):
        product_info["authenticity"] = "Guaranteed authentic"
    if getattr(product, "is_negotiable", False):
        product_info["negotiable"] = "Price negotiable"

    # Build corpus for downstream functions
    context_info["product"] = product
    context_info["corpus"] = build_corpus(product, context_info)

    # Audience, tone, keywords, and length
    context_info["target_audience"] = determine_target_audience_for_description(
        context_info["corpus"], context_info
    )
    context_info["tone"] = determine_writing_tone(context_info["corpus"], context_info)
    context_info["keywords"] = extract_keywords_for_description(context_info["corpus"])
    context_info["max_length"] = determine_max_length(
        context_info["corpus"], context_info
    )

    return product_info, context_info


def determine_target_audience_for_description(
    corpus: str, context_info: Dict[str, Any]
) -> str:
    """
    Determine a target audience string based on the combined text corpus.

    Applies segmentation rules and price fallbacks.

    Args:
        corpus: Lowercased text blob from build_corpus().
        context_info: Dict containing at least 'price'.

    Returns:
        A human-readable audience descriptor.
    """
    price = context_info.get("price", 0)

    # Rule-based segmentation
    if any(
        word in corpus for word in ["organic", "eco", "sustainable", "biodegradable"]
    ):
        return "eco-conscious and sustainability-minded consumers"

    # Electronics
    if any(word in corpus for word in ["phone", "smartphone", "iphone", "android"]):
        return "smartphone users and mobile technology enthusiasts"
    if any(word in corpus for word in ["laptop", "computer", "pc", "macbook"]):
        return "professionals and students seeking computing solutions"
    if any(word in corpus for word in ["headphones", "earbuds", "speaker", "audio"]):
        return "music lovers and audio enthusiasts"
    if any(word in corpus for word in ["camera", "photography", "lens"]):
        return "photographers and content creators"
    if any(word in corpus for word in ["gaming", "console", "game"]):
        return "gamers and entertainment enthusiasts"

    # Fashion and accessories
    if any(word in corpus for word in ["watch", "jewelry", "accessories"]):
        return "fashion-conscious individuals"
    if any(word in corpus for word in ["shoes", "sneakers", "boots"]):
        return "style-conscious shoppers"
    if any(word in corpus for word in ["clothing", "shirt", "dress", "jacket"]):
        return "fashion enthusiasts"

    # Home and living
    if any(word in corpus for word in ["furniture", "chair", "table", "sofa"]):
        return "homeowners and interior design enthusiasts"
    if any(word in corpus for word in ["kitchen", "appliance", "cookware"]):
        return "cooking enthusiasts and home chefs"
    if any(word in corpus for word in ["garden", "outdoor", "patio"]):
        return "outdoor living enthusiasts"

    # Sports and fitness
    if any(word in corpus for word in ["fitness", "exercise", "gym", "workout"]):
        return "fitness enthusiasts and health-conscious individuals"
    if any(word in corpus for word in ["sports", "athletic", "training"]):
        return "athletes and sports enthusiasts"

    # Automotive
    if any(word in corpus for word in ["car", "auto", "vehicle", "motorcycle"]):
        return "automotive enthusiasts and vehicle owners"

    # Price-based fallback
    if price and price > 1000:
        return "discerning customers seeking premium products"
    if price and price < 100:
        return "budget-conscious shoppers"

    return "quality-focused consumers"


def determine_writing_tone(corpus: str, context_info: Dict[str, Any]) -> str:
    """
    Determine writing tone based on corpus keywords and price thresholds.

    Args:
        corpus: Lowercased text blob from build_corpus().
        context_info: Dict containing at least 'price'.

    Returns:
        A tone label (e.g. 'professional', 'enthusiastic').
    """
    price = context_info.get("price", 0)
    for keywords, tone, min_p, max_p in TONE_RULES:
        if any(w in corpus for w in keywords):
            if (min_p is None or price >= min_p) and (max_p is None or price <= max_p):
                return tone

    # Fallbacks
    if price and price > 1000:
        return "luxurious"
    return "conversational"


def extract_keywords_for_description(corpus: str, max_keywords: int = 10) -> List[str]:
    """
    Extract top N meaningful keywords from corpus, excluding common commercial terms.

    Args:
        corpus: Lowercased text blob from build_corpus().
        max_keywords: Maximum number of keywords to return.

    Returns:
        A list of unique keyword strings.
    """
    words = re.findall(r"\b[a-z]{4,}\b", corpus)
    freq: Dict[str, int] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1

    reserved = {"buy", "best", "online", "quality"}
    candidates = [
        w for w in sorted(freq, key=freq.get, reverse=True) if w not in reserved
    ]

    return candidates[:max_keywords]


def determine_max_length(corpus: str, context_info: Dict[str, Any]) -> int:
    """
    Calculate a maximum description length based on category complexity and counts.
    """
    category = context_info.get("category", "").lower()
    product = context_info.get("product")

    # Use .all().count() if manager, else len() on list
    detail_count = 0
    details_manager = getattr(product, "product_details", None)
    if hasattr(details_manager, "count"):
        detail_count = details_manager.count()
    elif hasattr(details_manager, "__len__"):
        detail_count = len(details_manager)

    variant_count = 0
    variants_manager = getattr(product, "variants", None)
    if hasattr(variants_manager, "count"):
        variant_count = variants_manager.count()
    elif hasattr(variants_manager, "__len__"):
        variant_count = len(variants_manager)

    # Base caps
    if "electronics" in category:
        base = 500
    elif "fashion" in category:
        base = 300
    else:
        base = 400

    extra = detail_count * 20 + variant_count * 30
    return min(base + extra, 800)


def generate_fallback_description(
    product: Any, product_info: Dict[str, Any], description_type: str
) -> str:
    """
    Provide a simple fallback description template if AI generation fails.

    Args:
        product: Django model instance.
        product_info: Extracted product_info dict.
        description_type: One of 'meta', 'short', or 'marketing'.

    Returns:
        A plain-text description string.
    """
    title = product.title
    brand = product_info.get("brand", "")
    category = product_info.get("category", "")
    condition = product_info.get("condition", "")
    price = product_info.get("price", "")

    if description_type == "meta":
        return (
            f"Buy {title} online. {brand} {category} in {condition} condition. "
            "Great deals and fast shipping available!"
        )

    if description_type == "short":
        return (
            f"Premium {title} from {brand}. This {condition} {category} offers exceptional quality and value. "
            "Perfect for your needs with reliable performance. Order now for fast delivery!"
        )

    if description_type == "marketing":
        return (
            f"🔥 AMAZING DEAL! Get this {title} from {brand} at an unbeatable price! "
            f"This {condition} {category} is flying off our shelves. Don't miss out - order now and save big! ✨ FREE shipping included!"
        )

    # Default fallback
    return f"Discover this {title} today!"
