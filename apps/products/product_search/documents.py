from django_elasticsearch_dsl import Document, fields, Index
from django_elasticsearch_dsl.registries import registry
from apps.products.product_base.models import Product

# Elasticsearch index definition with custom analyzers and tokenizers
products_index = Index("products")
products_index.settings(
    number_of_shards=1,
    number_of_replicas=0,
    analysis={
        "analyzer": {
            "seo_analyzer": {
                "type": "custom",
                "tokenizer": "keyword",
                "filter": ["lowercase", "stop", "snowball"],
            },
            "autocomplete_analyzer": {
                "type": "custom",
                "tokenizer": "edge_ngram_tokenizer",
                "filter": ["lowercase"],
            },
        },
        "tokenizer": {
            "edge_ngram_tokenizer": {
                "type": "edge_ngram",
                "min_gram": 1,
                "max_gram": 20,
                "token_chars": ["letter", "digit"],
            }
        },
    },
)


@registry.register_document
class ProductDocument(Document):
    """
    Elasticsearch document for the Product model, aligned with the Django model,
    with full business logic in prepare methods for search text and popularity score.

    Overrides `update` to catch and log BulkIndexError details during indexing.
    """

    def update(self, thing, *args, **kwargs):
        """
        Override bulk update to catch and log indexing errors for debugging.
        """
        from elasticsearch.helpers import BulkIndexError
        import json

        try:
            return super().update(thing, *args, **kwargs)
        except BulkIndexError as e:
            for err in e.errors:
                print(json.dumps(err, indent=2, default=str))
            raise

    # Text and full-text fields
    title = fields.TextField(
        analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "suggest": fields.CompletionField(),
            "autocomplete": fields.TextField(analyzer="autocomplete_analyzer"),
        },
    )
    description = fields.TextField(
        analyzer="standard", fields={"raw": fields.KeywordField()}
    )
    search_text = fields.TextField(
        analyzer="standard",
        fields={"autocomplete": fields.TextField(analyzer="autocomplete_analyzer")},
    )

    # Identifiers and keywords
    slug = fields.KeywordField()
    short_code = fields.KeywordField()
    currency = fields.KeywordField()
    status = fields.KeywordField()

    # Pricing & discounts
    price = fields.FloatField(ignore_malformed=True)
    original_price = fields.FloatField(ignore_malformed=True)
    discount_percentage = fields.IntegerField()

    # Escrow & negotiation
    escrow_fee = fields.FloatField()
    escrow_hold_period = fields.IntegerField()
    is_negotiable = fields.BooleanField()
    requires_inspection = fields.BooleanField()
    negotiation_deadline = fields.DateField()
    max_negotiation_rounds = fields.IntegerField()

    # Shipping & guarantees
    requires_shipping = fields.BooleanField()
    authenticity_guaranteed = fields.BooleanField()
    warranty_period = fields.TextField()

    # Booleans
    is_active = fields.BooleanField()
    is_featured = fields.BooleanField()

    # Faceting: related model fields (UUIDs as Keywords)
    seller_id = fields.KeywordField(attr="seller_id")
    seller_username = fields.TextField(
        fields={"raw": fields.KeywordField()}, attr="seller.username"
    )
    category_id = fields.KeywordField(attr="category_id")
    category_name = fields.TextField(
        fields={"raw": fields.KeywordField()}, attr="category.name"
    )
    category_slug = fields.KeywordField(attr="category.slug")
    brand_id = fields.KeywordField(attr="brand_id")
    brand_name = fields.TextField(
        fields={"raw": fields.KeywordField()}, attr="brand.name"
    )
    condition_name = fields.TextField(
        fields={"raw": fields.KeywordField()}, attr="condition.name"
    )
    location = fields.TextField(fields={"raw": fields.KeywordField()}, attr="location")

    # Ratings
    average_rating = fields.FloatField()
    rating_count = fields.IntegerField()

    # Timestamps
    created_at = fields.DateField()
    updated_at = fields.DateField()

    # Popularity score
    popularity_score = fields.FloatField()

    class Index:
        name = products_index._name
        settings = products_index._settings

    class Django:
        model = Product
        # All fields explicitly declared above
        fields = []
        related_models = ["seller", "category", "brand", "condition"]

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("seller", "category", "brand", "condition")
        )

    def prepare_search_text(self, instance):
        """
        Combine multiple fields for comprehensive search:
        title, description, brand, category, condition, location, SEO keywords.
        """
        search_parts = []
        try:
            if instance.title:
                search_parts.append(instance.title)
            if instance.description:
                search_parts.append(instance.description)
            if instance.brand and instance.brand.name:
                search_parts.append(instance.brand.name)
            if instance.category and instance.category.name:
                search_parts.append(instance.category.name)
            if instance.condition and instance.condition.name:
                search_parts.append(instance.condition.name)
            if instance.location:
                search_parts.append(instance.location)
            meta = getattr(instance, "meta", None)
            if meta and getattr(meta, "seo_keywords", None):
                search_parts.append(meta.seo_keywords)
        except Exception:
            pass
        return " ".join(search_parts)

    def prepare_discount_percentage(self, instance):
        try:
            if (
                instance.original_price
                and instance.price
                and instance.original_price > 0
            ):
                return int(
                    (
                        (instance.original_price - instance.price)
                        / instance.original_price
                    )
                    * 100
                )
        except Exception:
            pass
        return 0

    def prepare_average_rating(self, instance):
        try:
            return (
                instance.average_rating()
                if callable(instance.average_rating)
                else instance.average_rating
            )
        except Exception:
            return 0.0

    def prepare_rating_count(self, instance):
        try:
            return (
                instance.rating_count()
                if callable(instance.rating_count)
                else instance.rating_count
            )
        except Exception:
            return 0

    def prepare_popularity_score(self, instance):
        """
        Calculate popularity based on views, ratings, feature flags, and authenticity:
        score = (views * 0.3) + (average_rating * rating_count * 0.4) +
                (is_featured * 100) + (authenticity_guaranteed * 50)
        """
        views = 0
        rating = 0.0
        rating_count = 0
        try:
            meta = getattr(instance, "meta", None)
            if meta and getattr(meta, "views_count", None):
                views = meta.views_count or 0
        except Exception:
            pass
        try:
            if callable(instance.average_rating):
                rating = instance.average_rating() or 0
            else:
                rating = instance.average_rating or 0
        except Exception:
            pass
        try:
            if callable(instance.rating_count):
                rating_count = instance.rating_count() or 0
            else:
                rating_count = instance.rating_count or 0
        except Exception:
            pass
        is_featured = 1 if getattr(instance, "is_featured", False) else 0
        authenticity = 1 if getattr(instance, "authenticity_guaranteed", False) else 0
        try:
            score = (
                (views * 0.3)
                + (rating * rating_count * 0.4)
                + (is_featured * 100)
                + (authenticity * 50)
            )
            return round(score, 2)
        except Exception:
            return 0.0
