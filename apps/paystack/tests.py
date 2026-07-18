import json
from decimal import Decimal
import pytest
from unittest.mock import patch
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.categories.models import Category
from apps.products.models import Product, ProductCondition
from apps.transactions.models import EscrowTransaction, FundHold
from apps.users.models import SellerPaymentProfile

User = get_user_model()


@pytest.mark.django_db
class TestPaystackEndpoints:

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = APIClient()
        self.buyer = User.objects.create_user(
            email="buyer@test.com", password="testpass123", first_name="Buyer"
        )
        self.seller = User.objects.create_user(
            email="seller@test.com", password="testpass123", first_name="Seller"
        )
        self.staff = User.objects.create_user(
            email="admin@test.com", password="adminpass123", is_staff=True
        )

        self.condition = ProductCondition.objects.create(name="New", slug="new")
        self.category = Category.objects.create(name="Electronics", slug="elec")
        
        self.product = Product.objects.create(
            title="Gadget",
            seller=self.seller,
            condition=self.condition,
            category=self.category,
            price=300.00,
        )

        self.transaction = EscrowTransaction.objects.create(
            product=self.product,
            buyer=self.buyer,
            seller=self.seller,
            tracking_id="MOCK-REF-999",
            price=300.00,
            total_amount=300.00,
            status=EscrowTransaction.STATUS_INITIATED,
        )

    def test_initialize_payment_success(self):
        self.client.force_authenticate(user=self.buyer)
        url = reverse("paystack:initialize-payment")
        response = self.client.post(url, {"transaction_id": self.transaction.id}, format="json")
        
        assert response.status_code == status.HTTP_200_OK
        assert "authorization_url" in response.data
        assert response.data["reference"] == "MOCK-REF-999"

    def test_resolve_account_success(self):
        self.client.force_authenticate(user=self.seller)
        url = reverse("paystack:resolve-account")
        response = self.client.get(url, {"account_number": "0123456789", "bank_code": "044"})
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data["account_name"] == "JOHN DOE ENTERPRISES"

    def test_register_seller_profile_success(self):
        self.client.force_authenticate(user=self.seller)
        url = reverse("paystack:register-seller")
        data = {
            "bank_name": "Access Bank",
            "bank_code": "044",
            "account_number": "0123456789"
        }
        response = self.client.post(url, data, format="json")
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["account_name"] == "JOHN DOE ENTERPRISES"
        assert response.data["data"]["recipient_code"].startswith("RCP_mock_rec_")
        
        # Verify db record
        profile = SellerPaymentProfile.objects.get(user=self.seller)
        assert profile.bank_name == "Access Bank"
        assert profile.paystack_recipient_code.startswith("RCP_mock_rec_")

    def test_webhook_charge_success(self):
        url = reverse("paystack:webhook")
        payload = {
            "event": "charge.success",
            "data": {
                "reference": "MOCK-REF-999",
                "status": "success",
                "amount": 30000
            }
        }
        
        # Webhook views are csrf_exempt. We call it without authentication.
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE="mock-sig"
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify transaction status was updated
        self.transaction.refresh_from_db()
        assert self.transaction.status == EscrowTransaction.STATUS_PAYMENT_RECEIVED
        
        # Verify escrow hold was placed
        assert FundHold.objects.filter(transaction=self.transaction, status=FundHold.STATUS_ACTIVE).exists()
