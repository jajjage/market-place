# Product Watchlist API Documentation

This API allows users to manage their product watchlists with full CRUD operations, bulk actions, and statistics.

## Base URL
```
/api/watchlist/
```

## Authentication
All endpoints require authentication. Include the authentication token in the header:
```
Authorization: Bearer <your-token>
```

---

## Endpoints

### 1. List Watchlist Items
**GET** `/api/watchlist/`

Get all watchlist items for the authenticated user.

#### Query Parameters
- `ordering` (optional): Order by field. Options: `added_at`, `-added_at`
- `user_id` (optional, staff only): View another user's watchlist

#### Response
```json
{
  "count": 25,
  "next": "http://api.example.com/watchlist/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "product": {
        "id": 123,
        "name": "Sample Product",
        "price": "99.99",
        "category": "Electronics"
      },
      "added_at": "2025-06-01T10:30:00Z"
    }
  ]
}
```

#### Cache
- **TTL**: 5 minutes
- **Varies on**: User cookie
- **Key pattern**: `product:list::user_id`

---

### 2. Get Watchlist Statistics
**GET** `/api/watchlist/stats/`

Get comprehensive statistics about the user's watchlist.

#### Query Parameters
- `user_id` (optional, staff only): Get stats for another user

#### Response
```json
{
  "total_items": 15,
  "recently_added": [123, 456, 789, 101, 112],
  "most_watched_categories": [
    {
      "name": "Electronics",
      "count": 8
    },
    {
      "name": "Clothing",
      "count": 4
    }
  ]
}
```

#### Cache
- **TTL**: 5 minutes
- **Key pattern**: `watchlist:stats:user_id`

---

### 3. Check Product in Watchlist
**GET** `/api/watchlist/check_product/`

Check if a specific product is in the user's watchlist.

#### Query Parameters
- `product_id` (required): ID of the product to check

#### Response
```json
{
  "in_watchlist": true
}
```

#### Cache
- **TTL**: 2.5 minutes (shorter due to frequent changes)
- **Key pattern**: `watchlist:check_product:user_id:product_id`

#### Error Responses
- `400 Bad Request`: Missing or invalid product_id
```json
{
  "error": "product_id parameter is required"
}
```

---

### 4. Toggle Product in Watchlist
**POST** `/api/watchlist/toggle_product/`

Add a product to watchlist if not present, remove if already present.

#### Request Body
```json
{
  "product_id": 123
}
```

#### Response (Added)
```json
{
  "status": "added",
  "message": "Product added to watchlist"
}
```
**Status Code**: `201 Created`

#### Response (Removed)
```json
{
  "status": "removed",
  "message": "Product removed from watchlist"
}
```
**Status Code**: `200 OK`

#### Cache Impact
Invalidates user and product-specific cache keys.

#### Error Responses
- `400 Bad Request`: Missing or invalid product_id
- `404 Not Found`: Product doesn't exist or is inactive

---

### 5. Bulk Operations
**POST** `/api/watchlist/bulk_operation/`

Perform bulk add or remove operations on multiple products.

#### Request Body (Bulk Add)
```json
{
  "operation": "add",
  "product_ids": [123, 456, 789]
}
```

#### Request Body (Bulk Remove)
```json
{
  "operation": "remove",
  "product_ids": [123, 456, 789]
}
```

#### Response (Bulk Add)
```json
{
  "message": "Added 3 products to your watchlist",
  "added_count": 3,
  "operation": "add"
}
```

#### Response (Bulk Remove)
```json
{
  "message": "Removed 2 products from your watchlist",
  "removed_count": 2,
  "operation": "remove"
}
```

#### Cache Impact
Invalidates user and all affected product cache keys.

---

### 6. Get Product Watchlist Count (Staff Only)
**GET** `/api/watchlist/by_product/`

Get the total number of users who have added a specific product to their watchlist.

#### Permissions
- **Staff only**: `is_staff=True` required

#### Query Parameters
- `product_id` (required): ID of the product

#### Response
```json
{
  "product_id": 123,
  "watchlist_count": 47
}
```

#### Cache
- **TTL**: 10 minutes (longer due to less frequent changes)
- **Key pattern**: `watchlist:product_count:product_id`

#### Error Responses
- `403 Forbidden`: Non-staff user
- `400 Bad Request`: Missing or invalid product_id

---

## Cache Strategy

### Cache Keys Pattern
```
watchlist:{view_name}:{user_id}:{product_id}
```

### Cache TTL
- **Default**: 5 minutes (300 seconds)
- **Check operations**: 2.5 minutes (150 seconds)
- **Product counts**: 10 minutes (600 seconds)

### Cache Invalidation
Cache is automatically invalidated when:
- User adds/removes products (toggle, bulk operations)
- Watchlist items are modified
- Related product data changes

### Configuration
Set in Django settings:
```python
WATCHLIST_CACHE_TTL = 300  # 5 minutes
```

---

## Error Handling

### Common Error Responses

#### 400 Bad Request
```json
{
  "error": "product_id parameter is required"
}
```

#### 401 Unauthorized
```json
{
  "detail": "Authentication credentials were not provided."
}
```

#### 403 Forbidden
```json
{
  "error": "Permission denied"
}
```

#### 404 Not Found
```json
{
  "detail": "Not found."
}
```

---

## Rate Limiting

Consider implementing rate limiting for:
- Toggle operations: 100 requests/hour
- Bulk operations: 20 requests/hour
- Check operations: 500 requests/hour

---

## Usage Examples

### JavaScript/Fetch API

#### Check if product is in watchlist
```javascript
const response = await fetch('/api/watchlist/check_product/?product_id=123', {
  headers: {
    'Authorization': 'Bearer ' + token
  }
});
const data = await response.json();
console.log(data.in_watchlist); // true/false
```

#### Toggle product in watchlist
```javascript
const response = await fetch('/api/watchlist/toggle_product/', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ' + token,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    product_id: 123
  })
});
const data = await response.json();
console.log(data.status); // "added" or "removed"
```

#### Get watchlist statistics
```javascript
const response = await fetch('/api/watchlist/stats/', {
  headers: {
    'Authorization': 'Bearer ' + token
  }
});
const stats = await response.json();
console.log(`Total items: ${stats.total_items}`);
```

### Python/Requests

#### Bulk add products
```python
import requests

response = requests.post(
    'https://api.example.com/watchlist/bulk_operation/',
    headers={'Authorization': f'Bearer {token}'},
    json={
        'operation': 'add',
        'product_ids': [123, 456, 789]
    }
)
data = response.json()
print(f"Added {data['added_count']} products")
```

---

## Performance Considerations

1. **Caching**: All read operations are cached with appropriate TTL
2. **Database Optimization**: Uses `select_related()` and `prefetch_related()`
3. **Bulk Operations**: Optimized with `bulk_create()` and proper conflict handling
4. **Query Optimization**: Minimal database queries with aggregations
5. **Cache Invalidation**: Smart invalidation only affects related cache keys

---

## Best Practices

1. **Use `toggle_product`** instead of separate add/remove endpoints
2. **Batch operations** with `bulk_operation` for multiple products
3. **Check cache headers** to avoid unnecessary requests
4. **Handle rate limits** gracefully in your client code
5. **Use `check_product`** before showing watchlist status in UI




<!-- from rest_framework import permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
from drf_spectacular.utils import extend_schema, OpenApiParameter -->
<!-- 
from apps.core.views import BaseViewSet
from apps.products.serializers import (
    ProductWatchlistItemListSerializer,
    ProductWatchlistItemDetailSerializer,
    ProductWatchlistBulkSerializer,
    WatchlistStatsSerializer,
)
from apps.products.services.product_watch_services import WatchlistService, CACHE_TTL
from apps.products.utils.rate_limiting import (
    AdminWatchlistThrottle,
    WatchlistBulkThrottle,
    WatchlistRateThrottle,
    WatchlistToggleThrottle,
    WatchlistThrottled,
    get_throttle_status,
)


class ProductWatchlistViewSet(BaseViewSet):
    """
    API endpoint for managing product watchlist items.
    Allows users to create and manage their product watchlists.
    """

    throttle_classes = [WatchlistRateThrottle]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["added_at"]
    ordering = ["-added_at"]

    def get_cache_key(self, view_name, **kwargs):
        """Generate a cache key for the view"""
        return f"product:{view_name}:{kwargs.get('pk', '')}:{kwargs.get('user_id', '')}"

    def get_queryset(self):
        """
        Return optimized watchlist items for the current user.
        """
        user = self.request.user
        user_id = None

        if user.is_staff and "user_id" in self.request.query_params:
            try:
                user_id = int(self.request.query_params.get("user_id"))
            except (ValueError, TypeError):
                pass

        return WatchlistService.get_user_watchlist_queryset(user, user_id)

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        serializer_mapping = {
            "list": ProductWatchlistItemListSerializer,
            "bulk_operation": ProductWatchlistBulkSerializer,
            "stats": WatchlistStatsSerializer,
        }
        return serializer_mapping.get(self.action, ProductWatchlistItemDetailSerializer)

    def get_permissions(self):
        """Custom permissions for watchlist access."""
        return [permissions.IsAuthenticated()]

    def handle_exception(self, exc):
        """Custom exception handling for throttling."""
        if hasattr(exc, 'default_code') and exc.default_code == 'throttled':
            # Convert DRF throttled exception to custom one
            scope = getattr(self.get_throttles()[0], 'scope', None) if self.get_throttles() else None
            raise WatchlistThrottled(wait=exc.wait, scope=scope)
        return super().handle_exception(exc)

    @method_decorator(cache_page(CACHE_TTL))
    @method_decorator(vary_on_cookie)
    def list(self, request, *args, **kwargs):
        """Get user's watchlist with caching."""
        response = super().list(request, *args, **kwargs)
        
        # Add throttle status to response
        throttle_status = get_throttle_status(request, WatchlistRateThrottle)
        if throttle_status:
            response.data['throttle_info'] = throttle_status
        
        return response

    @extend_schema(
        request=ProductWatchlistBulkSerializer,
        responses={200: {"description": "Bulk operation completed successfully"}},
    )
    @action(detail=False, methods=["post"], throttle_classes=[WatchlistBulkThrottle])
    def bulk_operation(self, request):
        """Perform bulk operations (add/remove) on watchlist items."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = serializer.save()

        if isinstance(result, list):
            response_data = {
                "message": f"Added {len(result)} products to your watchlist",
                "added_count": len(result),
                "operation": "add",
            }
        elif isinstance(result, dict) and "removed_count" in result:
            response_data = {
                "message": f"Removed {result['removed_count']} products from your watchlist",
                "removed_count": result["removed_count"],
                "operation": "remove",
            }
        else:
            response_data = result

        # Add throttle status to bulk operation response
        throttle_status = get_throttle_status(request, WatchlistBulkThrottle)
        if throttle_status:
            response_data['throttle_info'] = throttle_status

        return Response(response_data, status=status.HTTP_200_OK)

    @extend_schema(responses={200: WatchlistStatsSerializer})
    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get statistics about the user's watchlist with caching."""
        user = request.user
        user_id = None

        if user.is_staff and "user_id" in self.request.query_params:
            try:
                user_id = int(self.request.query_params.get("user_id"))
            except (ValueError, TypeError):
                pass

        stats = WatchlistService.get_watchlist_stats(user, user_id)
        serializer = self.get_serializer(stats)
        
        response_data = serializer.data
        
        # Add throttle status to stats response
        throttle_status = get_throttle_status(request, WatchlistRateThrottle)
        if throttle_status:
            response_data['throttle_info'] = throttle_status
        
        return Response(response_data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="product_id",
                description="Product ID to check",
                required=True,
                type=int,
            )
        ]
    )
    @action(detail=False, methods=["get"])
    def check_product(self, request):
        """Check if a product is in the user's watchlist with caching."""
        product_id = request.query_params.get("product_id")
        if not product_id:
            return Response(
                {"error": "product_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            product_id = int(product_id)
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid product_id format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_in_watchlist = WatchlistService.is_product_in_watchlist(
            request.user, product_id
        )

        response_data = {"in_watchlist": is_in_watchlist}
        
        # Add throttle status to check response
        throttle_status = get_throttle_status(request, WatchlistRateThrottle)
        if throttle_status:
            response_data['throttle_info'] = throttle_status

        return Response(response_data)

    @extend_schema(
        request={
            "type": "object",
            "properties": {"product_id": {"type": "integer"}},
            "required": ["product_id"],
        }
    )
    @action(detail=False, methods=["post"], throttle_classes=[WatchlistToggleThrottle])
    def toggle_product(self, request):
        """Toggle a product in the user's watchlist."""
        product_id = request.data.get("product_id")
        if not product_id:
            return Response(
                {"error": "product_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            product_id = int(product_id)
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid product_id format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = WatchlistService.toggle_product_in_watchlist(request.user, product_id)

        # Add throttle status to toggle response
        throttle_status = get_throttle_status(request, WatchlistToggleThrottle)
        if throttle_status:
            result['throttle_info'] = throttle_status

        response_status = (
            status.HTTP_201_CREATED
            if result["status"] == "added"
            else status.HTTP_200_OK
        )

        return Response(result, status=response_status)

    @action(detail=False, methods=["get"], throttle_classes=[AdminWatchlistThrottle])
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="product_id",
                description="Filter by product ID",
                required=True,
                type=int,
            )
        ]
    )
    def by_product(self, request):
        """Get watchlist count for a specific product (Staff only) with caching."""
        if not request.user.is_staff:
            return Response(
                {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
            )

        product_id = request.query_params.get("product_id")
        if not product_id:
            return Response(
                {"error": "product_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            product_id = int(product_id)
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid product_id format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        count = WatchlistService.get_product_watchlist_count(product_id)

        response_data = {"product_id": product_id, "watchlist_count": count}
        
        # Add throttle status to admin response
        throttle_status = get_throttle_status(request, AdminWatchlistThrottle)
        if throttle_status:
            response_data['throttle_info'] = throttle_status

        return Response(response_data) -->