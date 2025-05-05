"""
# Two-Step Product Creation with Social Sharing Support
---------------------------------------------------

This implementation provides a robust system for two-step product creation with:
1. Initial creation with just a title
2. Full updates after initial creation
3. Social media sharing functionality
4. Retrieval by short code and UUID

## API Endpoints

### Product Management
- `POST /api/products/` - Create product with just title
- `PATCH /api/products/{id}/` - Update product with full details
- `GET /api/products/` - List all products
- `GET /api/products/{id}/` - Get product details
- `DELETE /api/products/{id}/` - Delete product (owner only)

### Social Sharing
- `GET /api/products/{id}/get_share_links/` - Get shareable links for social media
- `GET /api/products/uuid/{uuid}/` - Get product by UUID
- `GET /api/products/{short_code}/` - Get product by short code (for social media)

### Watchlist Management
- `POST /api/products/{id}/add_to_watchlist/` - Add product to watchlist
- `DELETE /api/products/{id}/remove_from_watchlist/` - Remove from watchlist
- `GET /api/products/watchlist/` - Get products in watchlist
- `GET /api/watchlist/` - Get watchlist items directly

### User Products
- `GET /api/products/my_products/` - Get products created by current user

## Example Usage

### 1. Create a product with just title:

```http
POST /api/products/
Content-Type: application/json
Authorization: Bearer your_token_here

{
    "title": "New Gaming Laptop"
}
```

Response:
```json
{
    "id": 123,
    "title": "New Gaming Laptop",
    "short_code": "AbC1d2"
}
```

### 2. Update product with full details:

```http
PATCH /api/products/123/
Content-Type: application/json
Authorization: Bearer your_token_here

{
    "description": "High-performance gaming laptop with RTX 4080",
    "price": 1999.99,
    "original_price": 2499.99,
    "category": 5,
    "condition": 1,
    "is_active": true,
    "inventory_count": 10,
    "specifications": {
        "processor": "Intel i9",
        "ram": "32GB",
        "storage": "2TB SSD"
    }
}
```

### 3. Get share links:

```http
GET /api/products/123/get_share_links/
Authorization: Bearer your_token_here
```

Response:
```json
{
    "direct_link": "https://yoursite.com/products/AbC1d2/",
    "facebook": "https://www.facebook.com/sharer/sharer.php?u=https://yoursite.com/products/AbC1d2/?ref=facebook",
    "twitter": "https://twitter.com/intent/tweet?url=https://yoursite.com/products/AbC1d2/?ref=twitter&text=New Gaming Laptop",
    "whatsapp": "https://wa.me/?text=New Gaming Laptop - https://yoursite.com/products/AbC1d2/?ref=whatsapp",
    "linkedin": "https://www.linkedin.com/sharing/share-offsite/?url=https://yoursite.com/products/AbC1d2/?ref=linkedin",
    "telegram": "https://t.me/share/url?url=https://yoursite.com/products/AbC1d2/?ref=telegram&text=New Gaming Laptop"
}
```

### 4. Access product via short code:

```http
GET /api/products/AbC1d2/
```

The short code URL can be shared on social media, in emails, etc.

## Key Implementation Features

1. **Automatic Short Code Generation**: 
   Each product is assigned a unique short code on creation for easy sharing

2. **Social Sharing Tracking**:
   System tracks referrals from different platforms and counts views

3. **SEO-Friendly Slugs**:
   Product URLs include SEO-friendly slugs based on title

4. **Two-Step Creation**:
   Simplified product creation with minimal fields to start

5. **Proper Permission Handling**:
   - Anyone can view products
   - Only authenticated users can create/edit products
   - Only product owners can update their products
"""