# from django.test import TestCase
# import pytest
# from django.urls import reverse
# from rest_framework.test import APIClient
# from django.contrib.auth import get_user_model


# @pytest.mark.django_db
# def test_admin_can_crud_variant():
#     User = get_user_model()
#     admin = User.objects.create_user(username="admin", password="pass", is_staff=True)
#     client = APIClient()
#     client.force_authenticate(user=admin)

#     # Create
#     url = reverse("product-image-variant-list")
#     data = {"name": "thumb", "width": 100, "height": 100, "quality": 80}
#     resp = client.post(url, data)
#     assert resp.status_code == 201
#     variant_id = resp.data["id"]

#     # Read
#     resp = client.get(url)
#     assert resp.status_code == 200
#     assert any(v["id"] == variant_id for v in resp.data)

#     # Update
#     detail_url = reverse("product-image-variant-detail", args=[variant_id])
#     resp = client.patch(detail_url, {"quality": 90})
#     assert resp.status_code == 200
#     assert resp.data["quality"] == 90

#     # Delete
#     resp = client.delete(detail_url)
#     assert resp.status_code == 204


# @pytest.mark.django_db
# def test_non_staff_cannot_crud_variant():
#     User = get_user_model()
#     user = User.objects.create_user(username="user", password="pass", is_staff=False)
#     client = APIClient()
#     client.force_authenticate(user=user)
#     url = reverse("product-image-variant-list")
#     data = {"name": "thumb2", "width": 100, "height": 100, "quality": 80}
#     resp = client.post(url, data)
#     assert resp.status_code == 403
#     resp = client.get(url)
#     assert resp.status_code == 403
