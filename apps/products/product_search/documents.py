import json
from django_elasticsearch_dsl import Document, fields, Index
from django_elasticsearch_dsl.registries import registry
from django.contrib.auth import get_user_model
from apps.categories.models import Category
from apps.products.product_base.models import Product
from apps.products.product_brand.models import Brand
from apps.products.product_condition.models import ProductCondition
from apps.products.product_detail.models import ProductDetail

User = get_user_model()

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
    seo_keywords = fields.TextField(
        analyzer="standard",  # Standard analyzer will break keywords into individual terms
        fields={"raw": fields.KeywordField()},  # For exact phrase matching if needed
    )
    category_name = fields.KeywordField()

    details = fields.NestedField(
        properties={
            "label": fields.KeywordField(),  # Use Keyword for exact matching on labels like "RAM"
            "value": fields.TextField(  # Use TextField for full-text search on values
                fields={
                    "raw": fields.KeywordField()
                }  # And Keyword for exact matching/aggregations
            ),
            "unit": fields.KeywordField(),
        }
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
        # Ensure 'seo_keywords' is included in your Django model's attributes
        # that are mapped to Elasticsearch. You might use 'exclude' or 'fields'
        # based on your Django-Elasticsearch-DSL setup.
        # For simplicity, if using 'fields', ensure 'seo_keywords' is there.
        # If your Django model has a 'seo_keywords' field directly, it will be mapped.
        # If it's a related model, you'll need a 'prepare_seo_keywords' method.

        fields = []
        related_models = [
            User,
            Category,
            Brand,
            ProductCondition,
            ProductDetail,
        ]

    def save(self, **kwargs):
        # Prepare completion suggester data
        if hasattr(self, "title") and self.title:
            self.title.suggest = {
                "input": [self.title],
                "weight": getattr(self, "popularity_score", 1),
            }

        if hasattr(self, "brand_name") and self.brand_name:
            self.brand_name.suggest = {
                "input": [self.brand_name],
                "weight": 10,  # Brands get higher weight
            }

        if hasattr(self, "category_name") and self.category_name:
            self.category_name.suggest = {"input": [self.category_name], "weight": 5}

        return super().save(**kwargs)

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
            text_parts = [
                instance.title,
                instance.description,
                getattr(instance.category, "name", None),
                getattr(instance.brand, "name", None),
                getattr(instance.condition, "name", None),
                instance.location,
                self.prepare_seo_keywords(instance),  # Include prepared seo_keywords
            ]
        except Exception as e:
            print(f"Error preparing search text: {e}")
            text_parts = []
        search_parts.extend(filter(None, text_parts))
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

    def prepare_seo_keywords(self, instance):
        """
        Custom preparation method to handle seo_keywords from the Django model.
        """
        seo_keywords = getattr(instance, "seo_keywords", None)
        if seo_keywords:
            if isinstance(seo_keywords, list):
                return " ".join(seo_keywords)
            elif isinstance(seo_keywords, str):
                try:
                    # Handle legacy string format
                    parsed_keywords = json.loads(seo_keywords)
                    if isinstance(parsed_keywords, list):
                        return " ".join(parsed_keywords)
                    else:
                        return seo_keywords
                except json.JSONDecodeError:
                    return seo_keywords
        return None

    def prepare_category_name(self, instance):
        """Return the category's name."""
        if instance.category:
            return instance.category.name
        return None

    def prepare_details(self, instance):
        """
        Prepare the data for the 'details' NestedField.
        This method is called for each product instance being indexed.
        """
        # We query the database here, at INDEX time.
        details_queryset = instance.product_details.filter(is_active=True)
        return [
            {
                "label": detail.label,
                "value": detail.value,
                "unit": detail.unit,
            }
            for detail in details_queryset
        ]

    def get_instances_from_related(self, related_instance):
        """
        If a ProductDetail is saved or deleted, this finds the parent
        Product and tells Django-ES-DSL to re-index it.
        """
        if isinstance(related_instance, ProductDetail):
            return related_instance.product

        if isinstance(related_instance, User):
            return related_instance.products.all()

        if isinstance(related_instance, Category):
            return related_instance.products.all()

        if isinstance(related_instance, ProductCondition):
            return related_instance.products.all()

        if isinstance(related_instance, Brand):
            return related_instance.products.all()
