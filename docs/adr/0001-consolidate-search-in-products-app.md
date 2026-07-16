# 0001-consolidate-search-in-products-app

We decided to keep all search views, endpoints, and Elasticsearch index document mappings inside `apps/products/` and remove the empty `apps/search/` app. Since product search is tightly coupled with product categories, brands, conditions, and details, housing search in the products app prevents circular/cross-app dependencies and simplifies codebase navigation.
