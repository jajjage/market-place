import random
import string
from django.utils.text import slugify
from django.conf import settings
import uuid


def generate_short_code(rand_len=4, uuid_len=8):
    """
    Generate a composite short code:
      - rand_len random alphanumeric characters
      - uuid_len hex digits from a UUID4
    e.g. "aZ3f-1b2c3d4e"

    Args:
        rand_len:    how many purely random chars to prefix
        uuid_len:    how many hex chars from the UUID to suffix
    """
    chars = string.ascii_letters + string.digits
    rand_part = "".join(random.choice(chars) for _ in range(rand_len))
    uuid_part = uuid.uuid4().hex[:uuid_len]
    return f"{rand_part}-{uuid_part}"


def create_unique_short_code(model_class, length=6, max_attempts=10):
    """
    Create a unique short code that doesn't exist in the database.

    Args:
        model_class: The model class to check against
        length: Length of the short code (default: 6)
        max_attempts: Maximum number of attempts to generate a unique code

    Returns:
        A unique short code string
    """
    for _ in range(max_attempts):
        short_code = generate_short_code(length)

        # Check if this code already exists
        if not model_class.objects.filter(short_code=short_code).exists():
            return short_code

    # If we couldn't generate a unique code after max_attempts, increase length
    return create_unique_short_code(model_class, length + 1, max_attempts)


def generate_seo_friendly_slug(title):
    """
    Generate an SEO-friendly slug from a product title.

    Args:
        title: Product title

    Returns:
        An SEO-friendly slug
    """
    # Create base slug from title
    slug = slugify(title)

    # Add random suffix to ensure uniqueness
    random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"{slug}-{random_suffix}"


def build_social_meta_tags(product, request=None):
    """
    Build meta tags for social media sharing (Open Graph and Twitter cards).

    Args:
        product: The product object
        request: HTTP request object (for building absolute URLs)

    Returns:
        Dictionary of meta tags for social sharing
    """
    base_url = ""
    if request:
        base_url = request.build_absolute_uri("/")[
            :-1
        ]  # Get base URL without trailing slash

    # Get primary image URL
    image_url = f"{base_url}/media/product-placeholder.jpg"  # Default placeholder
    if product.images.exists():
        primary_image = product.images.first()
        if primary_image and primary_image.image:
            image_url = f"{base_url}{primary_image.image.url}"

    # Create social meta tags
    meta_tags = {
        # Open Graph tags
        "og:title": product.title,
        "og:description": (
            product.description[:200] + "..."
            if len(product.description) > 200
            else product.description
        ),
        "og:image": image_url,
        "og:url": f"{base_url}/products/{product.short_code}/",
        "og:type": "product",
        "og:price:amount": str(product.price),
        "og:price:currency": settings.DEFAULT_CURRENCY,
        # Twitter Card tags
        "twitter:card": "summary_large_image",
        "twitter:title": product.title,
        "twitter:description": (
            product.description[:200] + "..."
            if len(product.description) > 200
            else product.description
        ),
        "twitter:image": image_url,
    }

    return meta_tags
