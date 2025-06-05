from apps.core.utils.cache_manager import CacheKeyManager
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.urls import reverse
import urllib.parse
from apps.products.product_metadata.models import ProductMeta
from apps.products.product_base.models import Product


class ProductShareService:
    @staticmethod
    def get_share_links(view, request, short_code=None):
        cache_key = CacheKeyManager.make_key(
            "base", "share_links", short_code=short_code
        )
        cached_data = cache.get(cache_key)
        if cached_data:
            view.logger.info(f"Cache HIT for share links: {cache_key}")
            return view.success_response(data=cached_data)
        product = get_object_or_404(Product, short_code=short_code)
        meta, _ = ProductMeta.objects.get_or_create(product=product)
        meta.total_shares = (meta.total_shares or 0) + 1
        meta.save(update_fields=["total_shares"])
        product_path = reverse("product-detail-by-shortcode", args=[product.short_code])
        product_url = request.build_absolute_uri(product_path)
        url_enc = urllib.parse.quote_plus(product_url)
        title_enc = urllib.parse.quote_plus(product.title)
        share_links = {
            "direct": product_url,
            "facebook": f"https://www.facebook.com/sharer/sharer.php?u={url_enc}&ref=facebook",
            "twitter": f"https://twitter.com/intent/tweet?url={url_enc}&text={title_enc}&ref=twitter",
            "whatsapp": f"https://wa.me/?text={title_enc}%20-%20{url_enc}&ref=whatsapp",
            "linkedin": f"https://www.linkedin.com/sharing/share-offsite/?url={url_enc}&ref=linkedin",
            "telegram": f"https://t.me/share/url?url={url_enc}&text={title_enc}&ref=telegram",
        }
        cache.set(cache_key, share_links, view.CACHE_TTL)
        view.logger.info(f"Cached share links: {cache_key}")
        return view.success_response(data=share_links)
