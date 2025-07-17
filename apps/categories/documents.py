# In your categories app's documents.py

from django_elasticsearch_dsl import Document, fields, Index
from django_elasticsearch_dsl.registries import registry
from .models import Category

# Define the index for categories
categories_index = Index("categories")
categories_index.settings(number_of_shards=1, number_of_replicas=0)


@registry.register_document
class CategoryDocument(Document):
    """Elasticsearch document for the Category model."""

    name = fields.TextField(
        analyzer="standard",  # Keep this for general analysis
        fields={
            "raw": fields.KeywordField(),
            "suggest": fields.CompletionField(),
            # Add this field for partial matching
            "autocomplete": fields.TextField(analyzer="autocomplete_analyzer"),
        },
    )

    # Store parent info for building hierarchy
    parent_id = fields.KeywordField()
    parent_name = fields.KeywordField()

    class Index:
        name = "categories"
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
        model = Category
        fields = [
            "id",
            "slug",
            "description",
        ]

    def prepare_parent_id(self, instance):
        """Return the parent category's ID."""
        if instance.parent:
            return instance.parent.id
        return None

    def prepare_parent_name(self, instance):
        """Return the parent category's name."""
        if instance.parent:
            return instance.parent.name
        return ""

    def get_queryset(self):
        """Only index active categories."""
        return super().get_queryset().filter(is_active=True)
