# Elasticsearch & Django Integration Specification

This document details how Elasticsearch indexes are mapped and updated using `django-elasticsearch-dsl` inside the codebase.

---

## 1. Document Index Definitions

We define two main search indices inside [documents.py](file:///c:/Users/musta/fasu-marketplace/market-place/apps/products/documents.py):

### A. Brands Index (`brands`)
- **Document Class**: `BrandDocument`
- **Fields Index**: `id`, `slug`, `description`.
- **Searchable Fields**: `name` (includes standard keyword mapping, Completion Field for autocompletes, and custom autocomplete edge-ngram mappings).
- **Settings**: Single shard, zero replicas in dev.

### B. Products Index (`products`)
- **Document Class**: `ProductDocument`
- **Settings**: Single shard, custom EdgeNGram token analyzer with `min_gram=1` and `max_gram=20` to support fast incremental autocomplete search results.
- **Searchable Fields**:
  - `title`: Standard text with `.raw` keyword and `.autocomplete` ngram fields.
  - `description`: Full-text searchable.
  - `search_text`: Combined search field mapping title, descriptions, category, brand, and conditions.
  - `details`: Nested field mapping product attributes (`label`, `value`, `unit`).
  - `popularity_score`: Float field used to weight and sort search relevance.

---

## 2. Business Logic Prepare Methods

To avoid loading slow relational tables during runtime search queries, `ProductDocument` uses custom `prepare_*` methods at index-time to calculate or pre-join attributes:

*   **`prepare_search_text`**: Combines title, description, category name, brand name, condition name, and SEO keywords into a single indexable search string.
*   **`prepare_discount_percentage`**: Pre-calculates original price vs. current price markdown percentage.
*   **`prepare_popularity_score`**: Computes popularity rating based on product view counter (`meta__views_count`), review stars (`average_rating`), review count, and feature flags.
*   **`prepare_details`**: Prefetches active `ProductDetail` rows and formats them as a nested JSON list.

---

## 3. Relational Re-indexing & Signals

To prevent index data from becoming stale when related models change, `ProductDocument` defines a `related_models` registry. 

Modifying any of these models triggers re-indexing of the parent `Product` document via `get_instances_from_related`:
*   `User`: Updates seller username.
*   `Category`: Updates product category classifications.
*   `Brand`: Updates associated brand name.
*   `ProductCondition`: Updates condition name.
*   `ProductDetail`: Updates nested details list.

---

## 4. Rebuild & Populating Commands

Use these management commands to manage index lifecycles:
*   **Rebuild all indexes (drop + recreate + populate)**:
    ```bash
    poetry run python manage.py search_index --rebuild
    ```
*   **Populate specific index**:
    ```bash
    poetry run python manage.py search_index --populate --models=products.Product
    ```
*   **Create index structure only**:
    ```bash
    poetry run python manage.py search_index --create
    ```
