# Real-world usage examples for the ProductMeta services

"""
SCENARIO 1: User visits a product page
This is the most common scenario - when someone views a product detail page.
"""

# In your frontend, when a user visits /products/123/
# The product detail API call will automatically increment the view count:

# Frontend JavaScript:
# fetch('/api/v1/products/123/')
# .then(response => response.json())
# .then(data => {
#     // Product data is returned
#     // View count is automatically incremented
#     console.log('Product viewed:', data.name);
# });

# Backend (in ProductViewSet.retrieve):
def retrieve(self, request, *args, **kwargs):
    instance = self.get_object()
    
    # This happens automatically when someone views a product
    meta_services.increment_product_view_count(
        product_id=instance.id,
        use_cache_buffer=True  # Uses Redis buffering for performance
    )
    
    serializer = self.get_serializer(instance)
    return Response(serializer.data)


"""
SCENARIO 2: Product owner wants to optimize their product's SEO
A seller wants to add/update SEO metadata for their products.
"""

# Frontend: Owner goes to their dashboard and updates product SEO
# PUT /api/v1/products/123/manage-metadata/
# {
#     "meta_title": "Best Wireless Headphones 2024 - Premium Sound Quality",
#     "meta_description": "Experience crystal-clear audio with our premium wireless headphones. Long battery life, noise cancellation, and superior comfort.",
#     "seo_keywords": "wireless headphones, noise cancellation, premium audio, bluetooth headphones"
# }

# Backend handles it:
def manage_metadata(self, request, pk=None):
    instance = self.get_object()
    
    # Automatic ownership check
    if instance.owner != request.user:
        return Response({"error": "Not authorized"}, status=403)
    
    # Service handles the update with validation
    meta = meta_services.update_product_meta(
        product_id=instance.id,
        user=request.user,
        data=request.data
    )
    
    return Response(ProductMetaSerializer(meta).data)


"""
SCENARIO 3: Homepage showing featured products
Your homepage needs to show featured products with their view counts.
"""

# Frontend calls:
# GET /api/v1/product-metadata/featured/?limit=8

# Backend service:
def featured(self, request):
    limit = int(request.query_params.get("limit", 10))
    
    # Service automatically creates missing metadata for featured products
    queryset = services.get_featured_products_meta(limit=limit)
    
    # Returns products with metadata, sorted by view count
    serializer = self.get_serializer(queryset, many=True)
    return Response(serializer.data)


"""
SCENARIO 4: Seller dashboard showing their products' performance
A seller wants to see how their products are performing.
"""

# Frontend:
# GET /api/v1/product-metadata/my-products/

# Backend:
def my_products_meta(self, request):
    # Service automatically creates metadata for any products that don't have it
    queryset = services.get_user_products_meta(request.user)
    
    # Returns all their products with metadata (views, SEO status, etc.)
    serializer = self.get_serializer(queryset, many=True)
    return Response(serializer.data)


"""
SCENARIO 5: SEO-optimized product pages
When rendering product pages, you need SEO metadata for proper meta tags.
"""

# Frontend/Template needs SEO data:
# GET /api/v1/products/123/with-seo/

# Backend:
def with_seo(self, request, pk=None):
    instance = self.get_object()
    
    # Get product data
    product_data = ProductSerializer(instance).data
    
    # Get SEO metadata (creates if doesn't exist)
    meta = meta_services.get_product_meta_by_product(product_id=instance.id)
    product_data['seo_metadata'] = ProductMetaSerializer(meta).data
    
    # Track the view
    meta_services.increment_product_view_count(instance.id)
    
    return Response(product_data)

# Frontend can then use this for SEO:
# <title>{seo_metadata.meta_title || product.name}</title>  
# <meta name="description" content="{seo_metadata.meta_description}" />
# <meta name="keywords" content="{seo_metadata.seo_keywords}" />


"""
SCENARIO 6: Analytics dashboard
Admin wants to see product performance analytics.
"""

# GET /api/v1/product-metadata/stats/?min_views=100&ordering=-views_count

def stats(self, request):
    queryset = self.get_queryset()
    
    # Filter by minimum views
    min_views = request.query_params.get("min_views")
    if min_views:
        queryset = queryset.filter(views_count__gte=int(min_views))
    
    # Paginated response with metadata
    page = self.paginate_queryset(queryset)
    serializer = self.get_serializer(page, many=True)
    return self.get_paginated_response(serializer.data)


"""
SCENARIO 7: Asynchronous view tracking
For better performance, you might want to track views asynchronously.
"""

# Frontend can make a separate call to track views:
# POST /api/v1/product-analytics/123/track-view/

# This allows the main product page to load fast, then track the view separately
def track_view(self, request, pk=None):
    instance = self.get_object()
    
    # Non-blocking view tracking
    meta_services.increment_product_view_count(
        product_id=instance.id,
        use_cache_buffer=True  # Uses Redis buffer for performance
    )
    
    return Response({"status": "view tracked"})


"""
SCENARIO 8: Bulk operations for existing products
When you first implement this system, you need to create metadata for existing products.
"""

# Run this management command:
# python manage.py create_missing_metadata --dry-run  # Check what will be created
# python manage.py create_missing_metadata            # Actually create them

# Or call the service directly:
def setup_existing_products():
    # Creates metadata for all products that don't have it
    created_count = services.bulk_create_missing_metadata()
    print(f"Created metadata for {created_count} products")


"""
SCENARIO 9: Error handling and edge cases
Real-world applications need robust error handling.
"""

def safe_increment_view(product_id):
    try:
        meta_services.increment_product_view_count(
            product_id=product_id,
            use_cache_buffer=True
        )
    except ValueError as e:
        # Product doesn't exist or is inactive
        logger.warning(f"Cannot increment view for product {product_id}: {e}")
    except Exception as e:
        # Redis might be down, database error, etc.
        logger.error(f"Failed to increment view for product {product_id}: {e}")
        # Consider fallback to direct DB update
        try:
            meta_services.increment_product_view_count(
                product_id=product_id,
                use_cache_buffer=False  # Direct DB update
            )
        except Exception as fallback_error:
            logger.error(f"Fallback view increment failed: {fallback_error}")


"""
SCENARIO 10: Testing the services
Example of how to test these services.
"""

class TestProductMetaServices(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser')
        self.product = Product.objects.create(
            name='Test Product',
            owner=self.user,
            is_active=True
        )
    
    def test_increment_view_creates_metadata(self):
        # Ensure no metadata exists initially
        self.assertFalse(ProductMeta.objects.filter(product=self.product).exists())
        
        # Increment view count
        meta = meta_services.increment_product_view_count(self.product.id)
        
        # Metadata should be created
        self.assertTrue(ProductMeta.objects.filter(product=self.product).exists())
        self.assertEqual(meta.views_count, 1)
    
    def test_owner_can_update_metadata(self):
        meta = meta_services.update_product_meta(
            product_id=self.product.id,
            user=self.user,
            data={'meta_title': 'Updated Title'}
        )
        
        self.assertEqual(meta.meta_title, 'Updated Title')
    
    def test_non_owner_cannot_update_metadata(self):
        other_user = User.objects.create_user(username='otheruser')
        
        with self.assertRaises(PermissionDenied):
            meta_services.update_product_meta(
                product_id=self.product.id,
                user=other_user,
                data={'meta_title': 'Unauthorized Update'}
            )