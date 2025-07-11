from .get_env import env

# Elasticsearch Configuration
ELASTICSEARCH_DSL = {
    "default": {
        "hosts": [
            {
                "host": env.get("ELASTICSEARCH_HOST", default="elasticsearch"),
                "port": env.get("ELASTICSEARCH_PORT", default=9200, cast_to=int),
                "use_ssl": env.get(
                    "ELASTICSEARCH_USE_SSL", default=False, cast_to=bool
                ),
            }
        ],
        "timeout": 30,
        "max_retries": 3,
        "retry_on_timeout": True,
    },
    "SIGNAL_PROCESSOR": "django_elasticsearch_dsl.signals.RealTimeSignalProcessor",
}

# If using Elasticsearch Cloud or authentication
# if env.get("ELASTICSEARCH_USERNAME") and env.get("ELASTICSEARCH_PASSWORD"):
#     ELASTICSEARCH_DSL["default"]["http_auth"] = (
#         env.get("ELASTICSEARCH_USERNAME"),
#         env.get("ELASTICSEARCH_PASSWORD"),
#     )

# If using API key authentication
# if env.get("ELASTICSEARCH_API_KEY"):
#     ELASTICSEARCH_DSL["default"]["api_key"] = env.get("ELASTICSEARCH_API_KEY")

# Search Configuration
PRODUCT_SEARCH_SETTINGS = {
    "DEFAULT_PAGE_SIZE": 20,
    "MAX_PAGE_SIZE": 100,
    "AUTOCOMPLETE_MIN_LENGTH": 2,
    "AUTOCOMPLETE_MAX_SUGGESTIONS": 10,
    "SIMILAR_PRODUCTS_COUNT": 5,
    "TRENDING_PRODUCTS_COUNT": 10,
    "SEARCH_RESULT_CACHE_TTL": 300,  # 5 minutes
    "POPULAR_SEARCHES_LIMIT": 20,
    "SEO_KEYWORDS_MAX_LENGTH": 500,
    "ENABLE_SEARCH_ANALYTICS": True,
    "SEARCH_BOOST_FACTORS": {
        "title": 3.0,
        "brand": 2.0,
        "category": 2.0,
        "seo_keywords": 2.0,
        "description": 1.0,
        "search_text": 1.0,
    },
}
