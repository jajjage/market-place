# Categories API

This document outlines the API endpoints for managing product categories.

## Endpoints

### 1. List Categories

- **Endpoint:** `/categories/`
- **Method:** `GET`
- **Description:** Retrieves a list of top-level categories.

### 2. Retrieve a Category

- **Endpoint:** `/categories/{id}/`
- **Method:** `GET`
- **Description:** Retrieves the details of a specific category, including its subcategories and breadcrumbs.

### 3. Create a Category

- **Endpoint:** `/categories/`
- **Method:** `POST`
- **Description:** Creates a new category. To create a subcategory, provide the `parent` category's ID.
- **Request Body:**
  ```json
  {
    "name": "New Category",
    "description": "A description of the new category.",
    "parent": "parent_category_id"
  }
  ```

### 4. Update a Category

- **Endpoint:** `/categories/{id}/`
- **Method:** `PUT`
- **Description:** Updates an existing category.

### 5. Partially Update a Category

- **Endpoint:** `/categories/{id}/`
- **Method:** `PATCH`
- **Description:** Partially updates an existing category.

### 6. Delete a Category

- **Endpoint:** `/categories/{id}/`
- **Method:** `DELETE`
- **Description:** Deletes an existing category.

### 7. Get Category Tree

- **Endpoint:** `/categories/tree/`
- **Method:** `GET`
- **Description:** Retrieves a hierarchical tree of all categories.
- **Query Parameters:**
  - `depth` (integer, optional): The maximum depth of the tree to retrieve.
  - `include_inactive` (boolean, optional): Whether to include inactive categories.

### 8. Get Subcategories

- **Endpoint:** `/categories/{id}/subcategories/`
- **Method:** `GET`
- **Description:** Retrieves the direct subcategories of a specific category.

### 9. Get Category Breadcrumb

- **Endpoint:** `/categories/{id}/breadcrumb/`
- **Method:** `GET`
- **Description:** Retrieves the breadcrumb path for a specific category.

### 10. Get Category Products

- **Endpoint:** `/categories/{id}/products/`
- **Method:** `GET`
- **Description:** Retrieves the products belonging to a specific category.
- **Query Parameters:**
  - `include_subcategories` (boolean, optional): Whether to include products from subcategories.
  - `price_min` (float, optional): Minimum price filter.
  - `price_max` (float, optional): Maximum price filter.
  - `brand` (string, optional): Brand slug filter.
  - `in_stock` (boolean, optional): Whether to only include in-stock products.

### 11. Get Popular Categories

- **Endpoint:** `/categories/popular/`
- **Method:** `GET`
- **Description:** Retrieves the most popular categories based on product count.
- **Query Parameters:**
  - `limit` (integer, optional): The number of categories to return.
