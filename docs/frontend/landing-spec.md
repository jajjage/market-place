# Frontend Landing Page Specification

This document details the brand elements, landing page layout, interactive elements, and backend list-retrieval optimizations.

---

## 1. Page Structure

1.  **Navigation Bar**: Minimal transparent header, logo, page menus, login/signup actions.
2.  **Hero Section**: Full-width gradient, main CTAs ("Get Started", "Learn More"), floating statistics cards showing transaction metrics.
3.  **How It Works**: 3-step escrow cards (Secure Payment ➔ Protected Holding ➔ Safe Release).
4.  **Key Features Grid**: Buyer protection, Seller security, Dispute Resolution, Real-time chat.
5.  **Trust & Security**: Verification indicators, fraud guarantees, payment logo partners.
6.  **User Benefits**: Split layout showing value-props for Buyers vs. Sellers.
7.  **Footer**: Quick links, legal policies, social profiles, newsletter form.

---

## 2. Backend Caching & Query Optimization (Solving N+1 Queries)

To ensure the landing page and product search list load efficiently without causing database N+1 hits, the catalog retrieval service (`ProductListService`) enforces these strict query standards:

### Query Set Optimization
Our backend optimization pre-joins related models and fetches nested lists in a single SQL operation:
```python
# Eager loading related models
base_queryset = queryset.select_related(
    "brand",
    "category",
    "condition",
    "seller",
    "seller__profile",
    "meta",
).only(
    "id", "title", "price", "original_price", "currency", "slug", 
    "short_code", "is_active", "is_featured", "status", "description", 
    "location", "escrow_fee", "requires_inspection",
    "brand__id", "brand__name",
    "category__id", "category__name",
    "condition__id", "condition__name",
    "seller__id", "seller__first_name", "seller__last_name", "seller__email",
    "seller__profile__id", "seller__profile__avatar_url",
    "meta__id", "meta__views_count",
)
```

### Prefetching Nested Entities
Avoid executing individual queries for every image, variant, or review inside listings:
- **`primary_images`**: Prefetches only the active primary image.
- **`all_active_images`**: Prefetches all active images ordered by display rank.
- **`product_variants`**: Prefetches variants.
- **`approved_ratings`**: Prefetches only approved reviews with minimal reviewer profiles.

### Listing Cache Hashing
- **MD5 Param Hash**: A unique MD5 hash is generated from all filters (category, brand, condition, prices, page) to serve as the Redis cache key.
- **Cache Hits**: If the cache key hits, the serialized dictionary payload is returned immediately, bypassing database evaluation entirely.
