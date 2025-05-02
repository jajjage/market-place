# import pytest
# from django.urls import reverse
# from rest_framework import status
# from rest_framework.test import APIClient
# from decimal import Decimal
# from apps.products.models import (
#     Product,
#     Category,
#     ProductsStatus,
#     ProductCondition,
#     ProductImage,
#     ProductMeta,
# )
# import uuid
# from django.contrib.auth import get_user_model


# User = get_user_model()


# @pytest.fixture
# def api_client():
#     return APIClient()


# @pytest.fixture
# def create_user(db):
#     user = User.objects.create_user(
#         email="testuser@test.com",
#         password="testpassword123",
#         first_name="Test",
#         last_name="User",
#         user_type="SELLER",
#         verification_status="VERIFIED",
#     )
#     return user


# @pytest.fixture
# def user_data():
#     return {"email": "testuser@test.com", "password": "testpassword123"}


# @pytest.fixture
# def create_category(db):
#     category = Category.objects.create(
#         name="Test Category", description="Test Description"
#     )
#     return category


# @pytest.fixture
# def product_data(create_category):
#     return {
#         "title": "Test Product",
#         "description": "This is a test product",
#         "price": "99.99",
#         "compare_price": "129.99",
#         "currency": "USD",
#         "categories": [create_category.id],
#         "images": [{"url": "https://example.com/image1.jpg"}],
#         "specifications": {
#             "color": "blue",
#             "weight": "2kg",
#             "dimensions": "10x20x30cm",
#         },
#         "inventory_count": 100,
#         "is_featured": True,
#         "status": ProductsStatus.ACTIVE,
#     }


# @pytest.fixture
# def create_product(db, create_user, create_category):
#     """Create a test product with all required fields."""
#     product = Product.objects.create(
#         seller=create_user,
#         title="Test Product",
#         description="This is a test product",
#         price=Decimal("99.99"),
#         compare_price=Decimal("129.99"),
#         currency="USD",
#         inventory_count=100,
#         is_featured=True,
#         status=ProductsStatus.ACTIVE,
#         specifications={"color": "blue", "weight": "2kg", "dimensions": "10x20x30cm"},
#         category=create_category,
#         condition=ProductCondition.objects.create(
#             name="New", description="Brand new item"
#         ),
#     )

#     # Create an image for the product after it's created
#     ProductImage.objects.create(
#         product=product,
#         image="product_images/test_image.jpg",
#         is_primary=True,
#         display_order=0,
#     )

#     # Create metadata for the product
#     ProductMeta.objects.create(
#         product=product, views_count=0, featured=True, seo_keywords="test, product"
#     )

#     return product


# @pytest.mark.django_db
# class TestProductModel:
#     def test_product_creation(self, create_product):
#         """Test product creation and field values"""
#         product = create_product

#         assert product.title == "Test Product"
#         assert product.description == "This is a test product"
#         assert product.price == Decimal("99.99")
#         assert product.compare_price == Decimal("129.99")
#         assert product.currency == "USD"
#         assert product.inventory_count == 100
#         assert product.is_featured is True
#         assert product.status == ProductsStatus.ACTIVE
#         assert product.slug == "test-product"
#         assert product.short_code is not None
#         assert len(product.short_code) <= 10
#         assert product.categories.count() == 1
#         assert product.categories.first().name == "Test Category"

#     def test_product_string_representation(self, create_product):
#         """Test the string representation of a product"""
#         assert str(create_product) == "Test Product"

#     def test_product_slug_generation(self, create_user, create_category):
#         """Test automatic slug generation"""
#         product = Product.objects.create(
#             seller=create_user,
#             title="New Test Product With Spaces",
#             description="Description",
#             price=Decimal("19.99"),
#             currency="USD",
#             inventory_count=10,
#             status=ProductsStatus.DRAFT,
#         )
#         product.categories.add(create_category)

#         assert product.slug == "new-test-product-with-spaces"

#     def test_product_short_code_generation(self, create_user, create_category):
#         """Test automatic short code generation"""
#         product = Product.objects.create(
#             seller=create_user,
#             title="Short Code Test",
#             description="Description",
#             price=Decimal("19.99"),
#             currency="USD",
#             inventory_count=10,
#             status=ProductsStatus.DRAFT,
#         )
#         product.categories.add(create_category)

#         assert product.short_code is not None
#         assert len(product.short_code) <= 10

#     def test_product_get_absolute_url(self, create_product):
#         """Test the get_absolute_url method"""
#         url = create_product.get_absolute_url()
#         assert (
#             url == f"/products/{create_product.slug}/"
#         )  # Adjust if your URL pattern is different

#     def test_product_get_share_url(self, create_product, settings):
#         """Test the get_share_url method"""
#         settings.FRONTEND_DOMAIN = "https://example.com"
#         url = create_product.get_share_url()
#         assert url == f"https://example.com/p/{create_product.short_code}"


# @pytest.mark.django_db
# class TestProductViewSet:
#     def test_list_products(self, api_client, create_product):
#         """Test listing all products"""
#         url = reverse("product-list")
#         response = api_client.get(url)

#         assert response.status_code == status.HTTP_200_OK
#         assert len(response.data["results"]) == 1
#         assert response.data["results"][0]["title"] == "Test Product"

#     def test_retrieve_product(self, api_client, create_product):
#         """Test retrieving a specific product"""
#         url = reverse("product-detail", kwargs={"pk": create_product.id})
#         response = api_client.get(url)

#         assert response.status_code == status.HTTP_200_OK
#         assert response.data["title"] == "Test Product"
#         assert response.data["price"] == "99.99"
#         assert len(response.data["categories"]) == 1

#     def test_create_product_authenticated(self, authenticated_client, product_data):
#         """Test creating a product when authenticated"""
#         url = reverse("product-list")
#         response = authenticated_client.post(url, product_data, format="json")

#         assert response.status_code == status.HTTP_201_CREATED
#         assert response.data["title"] == "Test Product"
#         assert response.data["price"] == "99.99"
#         assert response.data["status"] == ProductsStatus.ACTIVE

#     def test_create_product_unauthenticated(self, api_client, product_data):
#         """Test creating a product when unauthenticated should fail"""
#         url = reverse("product-list")
#         response = api_client.post(url, product_data, format="json")

#         assert response.status_code == status.HTTP_401_UNAUTHORIZED

#     def test_update_product_owner(self, authenticated_client, create_product):
#         """Test updating a product as the owner"""
#         url = reverse("product-detail", kwargs={"pk": create_product.id})
#         data = {"title": "Updated Test Product", "price": "129.99"}
#         response = authenticated_client.patch(url, data, format="json")

#         assert response.status_code == status.HTTP_200_OK
#         assert response.data["title"] == "Updated Test Product"
#         assert response.data["price"] == "129.99"

#     def test_delete_product_owner(self, authenticated_client, create_product):
#         """Test deleting a product as the owner"""
#         url = reverse("product-detail", kwargs={"pk": create_product.id})
#         response = authenticated_client.delete(url)

#         assert response.status_code == status.HTTP_204_NO_CONTENT
#         assert Product.objects.filter(id=create_product.id).count() == 0


# @pytest.mark.django_db
# class TestProductDetailByUUID:
#     def test_retrieve_product_by_uuid(self, api_client, create_product):
#         """Test retrieving a product by UUID"""
#         url = reverse("product-detail-by-uuid", kwargs={"uuid": create_product.uuid})
#         response = api_client.get(url)

#         assert response.status_code == status.HTTP_200_OK
#         assert response.data["title"] == "Test Product"
#         assert uuid.UUID(response.data["uuid"]) == create_product.uuid


# @pytest.mark.django_db
# class TestProductDetailByShortCode:
#     def test_retrieve_product_by_short_code(self, api_client, create_product):
#         """Test retrieving a product by short code"""
#         url = reverse(
#             "product-detail-by-short-code",
#             kwargs={"short_code": create_product.short_code},
#         )
#         response = api_client.get(url)

#         assert response.status_code == status.HTTP_200_OK
#         assert response.data["title"] == "Test Product"
#         assert response.data["short_code"] == create_product.short_code
