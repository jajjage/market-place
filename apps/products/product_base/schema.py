from drf_spectacular.utils import OpenApiResponse, extend_schema, OpenApiExample
from apps.products.product_base.serializers import ProductDetailSerializer
from apps.products.product_base.serializers import ManageMetadataSerializer

PRODUCT_DETAIL_RESPONSE_SCHEMA = {
    200: OpenApiResponse(
        response=ProductDetailSerializer,
        description="Product details retrieved successfully",
        examples=[
            OpenApiExample(
                "Product Example",
                value={
                    "id": 1,
                    "title": "Sample Product",
                    "description": "A sample product description.",
                    "price": "19.99",
                    "created_at": "2024-06-01T12:00:00Z",
                    "updated_at": "2024-06-01T12:00:00Z",
                    "owner": "username",
                    "short_code": "abc123",
                    "share_url": "https://frontend.example.com/product/abc123",
                },
                status_codes=["200"],
            ),
        ],
    ),
    404: OpenApiResponse(
        description="Product not found",
        examples=[
            OpenApiExample(
                "Not Found",
                value={"detail": "Not found."},
                status_codes=["404"],
            ),
        ],
    ),
}

PRODUCT_LIST_RESPONSE_SCHEMA = {
    200: OpenApiResponse(
        response=ProductDetailSerializer(many=True),
        description="List of products",
        examples=[
            OpenApiExample(
                "Product List Example",
                value=[
                    {
                        "id": 1,
                        "title": "Sample Product",
                        "description": "A sample product description.",
                        "price": "19.99",
                        "created_at": "2024-06-01T12:00:00Z",
                        "updated_at": "2024-06-01T12:00:00Z",
                        "owner": "username",
                        "short_code": "abc123",
                        "share_url": "https://frontend.example.com/product/abc123",
                    }
                ],
                status_codes=["200"],
            ),
        ],
    ),
}

PRODUCT_MANAGE_METADATA = extend_schema(
    responses={
        200: ManageMetadataSerializer,
        403: OpenApiResponse(description="Not the owner of this product"),
        404: OpenApiResponse(description="Product not found"),
    }
)
