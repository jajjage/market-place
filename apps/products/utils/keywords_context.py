import re


def extract_product_keywords_and_context(product):
    """
    Extract keywords and context information from product to build seed term.
    Returns tuple of (seed_term, context_info)
    """
    keywords = []
    context_info = {}

    # Extract keywords from title (primary source for seed term)
    title_words = re.findall(r"\b\w+\b", product.title.lower())
    title_keywords = [word for word in title_words if len(word) > 2]
    keywords.extend(title_keywords)

    # Build primary seed term from title (first 2-3 most meaningful words)
    seed_term = " ".join(title_keywords[:3]) if title_keywords else product.title

    # Add brand if available
    if product.brand:
        brand_name = product.brand.name.lower()
        keywords.append(brand_name)
        context_info["brand"] = product.brand.name

    # Add category if available
    if product.category:
        category_name = product.category.name.lower()
        keywords.append(category_name)
        context_info["category"] = product.category.name

        # Update seed term to include category if it's not already there
        if category_name not in seed_term.lower():
            seed_term = f"{category_name} {seed_term}"

    # Add condition
    if product.condition:
        condition_name = product.condition.name.lower()
        keywords.append(condition_name)
        context_info["condition"] = product.condition.name

    # Add location keywords
    if product.location:
        location_words = re.findall(r"\b\w+\b", product.location.lower())
        location_keywords = [word for word in location_words if len(word) > 2]
        keywords.extend(location_keywords)
        context_info["location"] = product.location

    # Add price-related context
    if product.price:
        if product.price < 100:
            keywords.append("affordable")
            context_info["price_range"] = "budget"
        elif product.price > 1000:
            keywords.append("premium")
            context_info["price_range"] = "premium"
        else:
            context_info["price_range"] = "mid-range"

    # Add condition-specific keywords
    if hasattr(product, "authenticity_guaranteed") and product.authenticity_guaranteed:
        keywords.extend(["authentic", "genuine", "original"])
        context_info["authenticity"] = True

    if hasattr(product, "is_negotiable") and product.is_negotiable:
        keywords.extend(["negotiable", "best offer"])
        context_info["negotiable"] = True

    # Add descriptive keywords from description
    if product.description:
        desc_words = re.findall(r"\b\w+\b", product.description.lower())
        # Filter for meaningful words (longer than 3 chars, not common words)
        common_words = {
            "the",
            "and",
            "for",
            "are",
            "but",
            "not",
            "you",
            "all",
            "can",
            "had",
            "her",
            "was",
            "one",
            "our",
            "out",
            "day",
            "get",
            "has",
            "him",
            "his",
            "how",
            "man",
            "new",
            "now",
            "old",
            "see",
            "two",
            "way",
            "who",
            "boy",
            "did",
            "its",
            "let",
            "put",
            "say",
            "she",
            "too",
            "use",
            "this",
            "that",
            "with",
            "have",
            "from",
            "they",
            "know",
            "want",
            "been",
            "good",
            "much",
            "some",
            "time",
            "very",
            "when",
            "come",
            "here",
            "just",
            "like",
            "long",
            "make",
            "many",
            "over",
            "such",
            "take",
            "than",
            "them",
            "well",
            "were",
        }
        meaningful_words = [
            word for word in desc_words if len(word) > 3 and word not in common_words
        ]
        keywords.extend(meaningful_words[:10])  # Limit to top 10

    # Determine target audience based on product characteristics
    target_audience = determine_target_audience(product, context_info)
    context_info["target_audience"] = target_audience

    # Clean up seed term
    seed_term = clean_seed_term(seed_term)

    return seed_term, context_info


def determine_target_audience(product, context_info):
    """
    Determine target audience based on product characteristics.
    """
    title_lower = product.title.lower()
    category = context_info.get("category", "").lower()
    price_range = context_info.get("price_range", "mid-range")

    # Electronics
    if any(
        word in title_lower
        for word in ["phone", "laptop", "camera", "headphones", "speaker"]
    ):
        if price_range == "premium":
            return "tech enthusiasts and professionals"
        else:
            return "tech-savvy consumers"

    # Fashion
    if any(
        word in title_lower for word in ["shirt", "dress", "shoes", "jacket", "fashion"]
    ):
        if price_range == "premium":
            return "fashion-conscious professionals"
        else:
            return "style-conscious shoppers"

    # Home & Garden
    if any(word in title_lower for word in ["furniture", "home", "decor", "kitchen"]):
        return "homeowners and interior design enthusiasts"

    # Sports & Fitness
    if any(word in title_lower for word in ["fitness", "sports", "exercise", "gym"]):
        return "fitness enthusiasts and athletes"

    # Automotive
    if any(word in title_lower for word in ["car", "auto", "vehicle", "motorcycle"]):
        return "automotive enthusiasts"

    # Default based on price range
    if price_range == "budget":
        return "budget-conscious shoppers"
    elif price_range == "premium":
        return "premium product buyers"
    else:
        return "general consumers"


def clean_seed_term(seed_term):
    """
    Clean and optimize the seed term for better AI generation.
    """
    # Remove extra spaces and special characters
    seed_term = re.sub(r"[^\w\s-]", "", seed_term)
    seed_term = re.sub(r"\s+", " ", seed_term).strip()

    # Limit length to prevent overly long seed terms
    words = seed_term.split()
    if len(words) > 4:
        seed_term = " ".join(words[:4])

    return seed_term


def generate_fallback_keywords(product, seed_term):
    """
    Generate fallback keywords if AI service fails.
    """
    keywords = []

    # Basic prefixes and suffixes
    prefixes = [
        "buy",
        "best",
        "cheap",
        "quality",
        "professional",
        "top",
        "good",
        "new",
        "used",
    ]
    suffixes = [
        "online",
        "store",
        "deals",
        "reviews",
        "guide",
        "tips",
        "near me",
        "for sale",
    ]

    # Generate prefix combinations
    for prefix in prefixes[:6]:
        keywords.append(f"{prefix} {seed_term}")

    # Generate suffix combinations
    for suffix in suffixes[:6]:
        keywords.append(f"{seed_term} {suffix}")

    # Add brand-specific keywords if available
    if product.brand:
        keywords.extend(
            [
                f"{product.brand.name} {seed_term}",
                f"buy {product.brand.name} {seed_term}",
                f"best {product.brand.name} {seed_term}",
            ]
        )

    # Add category-specific keywords if available
    if product.category:
        keywords.extend(
            [
                f"{product.category.name} {seed_term}",
                f"buy {product.category.name}",
                f"best {product.category.name}",
            ]
        )

    # Add location-based keywords if available
    if product.location:
        keywords.extend(
            [
                f"{seed_term} in {product.location}",
                f"buy {seed_term} {product.location}",
                f"{seed_term} near {product.location}",
            ]
        )

    # Add some long-tail variations
    keywords.extend(
        [
            f"how to buy {seed_term}",
            f"where to buy {seed_term}",
            f"{seed_term} comparison",
            f"{seed_term} benefits",
            f"affordable {seed_term}",
            f"discount {seed_term}",
        ]
    )

    # Remove duplicates while preserving order
    seen = set()
    unique_keywords = []
    for keyword in keywords:
        if keyword.lower() not in seen:
            seen.add(keyword.lower())
            unique_keywords.append(keyword)

    return unique_keywords
