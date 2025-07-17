from django_elasticsearch_dsl import Document, fields, Index
from django_elasticsearch_dsl.registries import registry
from .models import Brand

# Define the index for brands
brands_index = Index("brands")
brands_index.settings(number_of_shards=1, number_of_replicas=0)


@registry.register_document
class BrandDocument(Document):
    """Elasticsearch document for the Brand model."""

    # We want to search by name, so we define it as a TextField
    # with a .raw keyword field for exact matches and sorting,
    # and a .suggest field for autocomplete.
    name = fields.TextField(
        analyzer="standard",  # Keep this for general analysis
        fields={
            "raw": fields.KeywordField(),
            "suggest": fields.CompletionField(),
            # Add this field for partial matching
            "autocomplete": fields.TextField(analyzer="autocomplete_analyzer"),
        },
    )

    # We store the logo URL for easy display in search results
    logo_url = fields.KeywordField()

    # Basic info for filtering or display
    country_of_origin = fields.KeywordField()
    is_featured = fields.BooleanField()
    cached_product_count = fields.IntegerField()

    class Index:
        name = "brands"
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            # IMPORTANT: Copy the analysis settings from your Product index
            "analysis": {
                "analyzer": {
                    "autocomplete_analyzer": {
                        "type": "custom",
                        "tokenizer": "edge_ngram_tokenizer",
                        "filter": ["lowercase"],
                    },
                },
                "tokenizer": {
                    "edge_ngram_tokenizer": {
                        "type": "edge_ngram",
                        "min_gram": 2,  # Start from 2 characters for better performance
                        "max_gram": 20,
                        "token_chars": ["letter", "digit"],
                    }
                },
            },
        }

    class Django:
        model = Brand
        # List only the fields we want in our Elasticsearch index
        fields = [
            "id",
            "slug",
            "description",
        ]

    def prepare_logo_url(self, instance):
        """Prepare the full URL for the brand's logo."""
        if instance.logo:
            return instance.logo.url
        return None

    def get_queryset(self):
        """
        Return the queryset of objects to be indexed.
        Only index active brands.
        """
        return super().get_queryset().filter(is_active=True)
