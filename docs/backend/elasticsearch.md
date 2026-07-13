# Elasticsearch & Django Integration

This guide provides details of how Elasticsearch is integrated with the Django application via `django-elasticsearch-dsl` for search-powered catalog queries.

---

## 1. Core Integration Concepts

- **Indices as Tables**: Documents represent JSON documents stored within indices.
- **Auto-Sync via Signals**: The framework uses Django model post-save/delete signals to index or remove documents from Elasticsearch in real-time.
- **Registry**: Document classes are registered using the registry decorator:
  ```python
  from django_elasticsearch_dsl.registries import registry
  @registry.register_document
  class ProductDocument(Document):
      # ...
  ```

---

## 2. Typical Document Mapping Layout

For catalog indexing, the document class maps fields and specifies analyzers (e.g. edge-ngram for autocompletes):
```python
class Index:
    name = 'products'
    settings = {
        'number_of_shards': 1,
        'number_of_replicas': 0
    }

class Django:
    model = Product
    fields = [
        'title',
        'description',
        'price',
        'status',
    ]
```

---

## 3. Management Commands

- **Create index mapping**:
  ```bash
  python manage.py search_index --create
  ```
- **Populate existing data**:
  ```bash
  python manage.py search_index --populate
  ```
- **Rebuild index (Re-create + Re-populate)**:
  ```bash
  python manage.py search_index --rebuild
  ```
