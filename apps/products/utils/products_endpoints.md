# Product Endpoints Documentation

## Base Endpoints

### List Products
- **URL:** `/api/products/`
- **Method:** GET
- **Description:** List all active products with pagination and filtering
- **Filters:**
  - `min_price`: Minimum price filter
  - `max_price`: Maximum price filter
  - `has_discount`: Filter products with discounts (boolean)
  - `min_discount_percentage`: Minimum discount percentage
  - `created_after`: DateTime filter for products created after
  - `created_before`: DateTime filter for products created before
  - `title_contains`: Search in title
  - `description_contains`: Search in description
  - `seller_email`: Filter by seller's email
  - `category_name`: Filter by category name
  - `specification_value`: Filter by specification (format: key:value)
  - `search`: Global search across title, description, seller email, category
- **Ordering:** price, created_at, title, inventory_count

### Get Single Product
- **URL:** `/api/products/{id}/`
- **Method:** GET
- **Description:** Get detailed information about a specific product
- **Response:** Detailed product information including images, specifications, seller details

### Create Product
- **URL:** `/api/products/`
- **Method:** POST
- **Permission:** SELLER only
- **Request Body:**
  ```json
  {
    "title": "string (required)",
    "description": "string",
    "price": "decimal",
    "compare_price": "decimal",
    "currency": "string",
    "categories": ["id"],
    "images": "json",
    "specifications": "json",
    "inventory_count": "integer"
  }
  ```

### Update Product
- **URL:** `/api/products/{id}/`
- **Method:** PUT/PATCH
- **Permission:** SELLER only
- **Request Body:** Same as Create Product

## Seller-Specific Endpoints

### My Products
- **URL:** `/api/products/my-products/`
- **Method:** GET
- **Permission:** SELLER only
- **Description:** Get current seller's products
- **Filters:** status

### Product Statistics
- **URL:** `/api/products/stats/`
- **Method:** GET
- **Permission:** SELLER only
- **Description:** Get comprehensive product statistics including:
  - Total products count
  - Active/Featured products
  - Inventory statistics
  - Category distribution
  - Discount statistics
  - Monthly trends

### Toggle Product Status
- **URL:** `/api/products/{id}/toggle-active/`
- **Method:** POST
- **Permission:** SELLER only
- **Description:** Toggle product active status

### Toggle Featured Status
- **URL:** `/api/products/{id}/toggle-featured/`
- **Method:** POST
- **Permission:** SELLER only
- **Description:** Toggle product featured status

## Inventory Management Endpoints

### Add Inventory
- **URL:** `/api/products/{id}/add-inventory/`
- **Method:** POST
- **Permission:** SELLER only
- **Request Body:**
  ```json
  {
    "quantity": "integer (required)",
    "notes": "string"
  }
  ```

### Activate Inventory
- **URL:** `/api/products/{id}/activate-inventory/`
- **Method:** POST
- **Permission:** SELLER only
- **Description:** Move inventory from total to available
- **Request Body:** Same as Add Inventory

### Place in Escrow
- **URL:** `/api/products/{id}/place-in-escrow/`
- **Method:** POST
- **Permission:** BUYER only
- **Request Body:** Same as Add Inventory

### Release from Escrow
- **URL:** `/api/products/{id}/release-from-escrow/`
- **Method:** POST
- **Permission:** SELLER only
- **Request Body:** Same as Add Inventory

## Price Negotiation Endpoints

### Initiate Negotiation
- **URL:** `/api/products/{id}/initiate-negotiation/`
- **Method:** POST
- **Permission:** BUYER only
- **Request Body:**
  ```json
  {
    "offered_price": "decimal (required)"
  }
  ```
- **Response:**
  ```json
  {
    "negotiation_id": "string",
    "product": {
      "id": "string",
      "name": "string",
      "original_price": "decimal"
    },
    "offered_price": "decimal",
    "status": "string",
    "seller": "string",
    "created_at": "datetime"
  }
  ```

### Respond to Negotiation
- **URL:** `/api/products/respond-to-negotiation/{negotiation_id}/`
- **Method:** POST
- **Permission:** SELLER only
- **Request Body:**
  ```json
  {
    "response_type": "string (accept/reject/counter)",
    "counter_price": "decimal (required for counter response)"
  }
  ```

### Create Transaction from Negotiation
- **URL:** `/api/products/create-transaction/{negotiation_id}/`
- **Method:** POST
- **Permission:** BUYER only
- **Description:** Create transaction after successful negotiation
- **Request Body:**
  ```json
  {
    "quantity": "integer (required)",
    "notes": "string"
  }
  ```

## Social Sharing Endpoints

### Get Share Links
- **URL:** `/api/products/share-links/{short_code}/`
- **Method:** GET
- **Description:** Generate social media sharing links
- **Response:** URLs for sharing on various platforms (Facebook, Twitter, WhatsApp, LinkedIn, Telegram)

### Product by Short Code
- **URL:** `/api/products/by-shortcode/{short_code}/`
- **Method:** GET
- **Description:** Public endpoint to view product by its short code
- **Features:** Tracks views and share statistics

## Featured Products

### List Featured Products
- **URL:** `/api/products/featured/`
- **Method:** GET
- **Description:** Get list of featured products
- **Access:** Public