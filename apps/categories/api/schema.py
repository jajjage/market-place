# apps/categories/api/schema.py
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse


# Import your actual serializers
from apps.categories.api.serializers import (
    CategoryTreeSerializer,
    CategoryListSerializer,
    CategoryBreadcrumbSerializer,
    # Add other serializers as needed
)

category_viewset_schema = {
    "list": {
        "summary": "List Categories",
        "description": "Retrieve a list of top-level categories.",
    },
    "retrieve": {
        "summary": "Retrieve a Category",
        "description": (
            "Retrieve details of a specific category, "
            "including its subcategories and breadcrumbs."
        ),
    },
    "create": {
        "summary": "Create a Category",
        "description": (
            "Create a new category. The parent field can be used to create a subcategory."
        ),
    },
    "update": {
        "summary": "Update a Category",
        "description": "Update an existing category.",
    },
    "partial_update": {
        "summary": "Partially Update a Category",
        "description": "Partially update an existing category.",
    },
    "destroy": {
        "summary": "Delete a Category",
        "description": "Delete an existing category.",
    },
    "tree": {
        "summary": "Get Category Tree",
        "description": "Get a hierarchical tree of all categories.",
        "parameters": [
            OpenApiParameter(
                "depth",
                description="Maximum depth of the tree.",
                type=int,
                required=False,
            ),
            OpenApiParameter(
                "include_inactive",
                description="Include inactive categories.",
                type=bool,
                required=False,
            ),
        ],
        "responses": {
            200: OpenApiResponse(
                response=CategoryTreeSerializer(many=True),
                description="List of categories in tree structure",
            )
        },
    },
    "subcategories": {
        "summary": "Get Subcategories",
        "description": "Get the direct subcategories of a specific category.",
        "responses": {
            200: OpenApiResponse(
                response=CategoryListSerializer(many=True),
                description="List of subcategories",
            )
        },
    },
    "breadcrumb": {
        "summary": "Get Category Breadcrumb",
        "description": "Get the breadcrumb path for a specific category.",
        "responses": {
            200: OpenApiResponse(
                response=CategoryBreadcrumbSerializer(many=True),
                description="Breadcrumb path for the category",
            )
        },
    },
    "products": {
        "summary": "Get Category Products",
        "description": "Get the products belonging to a specific category.",
        "parameters": [
            OpenApiParameter(
                "include_subcategories",
                description="Include products from subcategories.",
                type=bool,
                required=False,
            ),
            OpenApiParameter(
                "price_min",
                description="Minimum price filter.",
                type=float,
                required=False,
            ),
            OpenApiParameter(
                "price_max",
                description="Maximum price filter.",
                type=float,
                required=False,
            ),
            OpenApiParameter(
                "brand", description="Brand slug filter.", type=str, required=False
            ),
            OpenApiParameter(
                "in_stock",
                description="Only in-stock products.",
                type=bool,
                required=False,
            ),
        ],
        "responses": {
            200: OpenApiResponse(
                response=CategoryListSerializer(many=True),
                description="List of products in the category",
            )
        },
    },
    "popular": {
        "summary": "Get Popular Categories",
        "description": "Get the most popular categories based on product count.",
        "parameters": [
            OpenApiParameter(
                "limit",
                description="Number of categories to return.",
                type=int,
                required=False,
            ),
        ],
        "responses": {
            200: OpenApiResponse(
                response=CategoryListSerializer(many=True),
                description="List of popular categories",
            )
        },
    },
}
