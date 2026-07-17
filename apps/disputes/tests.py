from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.disputes.services import DisputeService
from apps.disputes.models import Dispute, DisputeReason
from apps.transactions.models import EscrowTransaction
from apps.products.models import Product, ProductCondition, Brand
from apps.categories.models import Category

User = get_user_model()


class DisputeServiceTest(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            email="buyer@test.com", password="testpass123"
        )
        self.seller = User.objects.create_user(
            email="seller@test.com", password="testpass123"
        )
        self.condition = ProductCondition.objects.create(name="New", slug="new")
        self.category = Category.objects.create(name="Test Category", slug="test-cat")
        self.brand = Brand.objects.create(name="Test Brand", slug="test-brand")
        self.product = Product.objects.create(
            title="Test Product",
            seller=self.seller,
            condition=self.condition,
            category=self.category,
            brand=self.brand,
            price=100.00,
            requires_inspection=True,
        )
        # Create transaction in inspection state
        self.transaction = EscrowTransaction.objects.create(
            product=self.product,
            buyer=self.buyer,
            seller=self.seller,
            tracking_id="TRK-TEST-DISP",
            price=100.00,
            status="inspection",
            status_changed_at=timezone.now(),
        )

    def test_dispute_creation_transitions_transaction(self):
        dispute = DisputeService.create_dispute(
            transaction_id=self.transaction.id,
            user=self.buyer,
            reason=DisputeReason.NOT_AS_DESCRIBED,
            description="Item is damaged",
        )
        self.assertEqual(dispute.transaction.status, "disputed")
        # Reload transaction from DB
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, "disputed")

    def test_resolve_dispute_for_buyer_transitions_to_refunded(self):
        # Create the dispute first
        dispute = DisputeService.create_dispute(
            transaction_id=self.transaction.id,
            user=self.buyer,
            reason=DisputeReason.NOT_AS_DESCRIBED,
            description="Item is damaged",
        )
        
        # Create a staff user to resolve the dispute
        staff_user = User.objects.create_superuser(
            email="staff@test.com", password="staffpass123"
        )
        
        # Resolve dispute for buyer
        DisputeService.resolve_dispute(
            dispute_id=dispute.id,
            resolver_user=staff_user,
            status="resolved_buyer",
            resolution_note="Refund approved",
        )
        
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, "refunded")

    def test_resolve_dispute_for_seller_transitions_to_completed(self):
        dispute = DisputeService.create_dispute(
            transaction_id=self.transaction.id,
            user=self.buyer,
            reason=DisputeReason.NOT_AS_DESCRIBED,
            description="Item is damaged",
        )
        
        staff_user = User.objects.create_superuser(
            email="staff@test.com", password="staffpass123"
        )
        
        # Resolve dispute for seller
        DisputeService.resolve_dispute(
            dispute_id=dispute.id,
            resolver_user=staff_user,
            status="resolved_seller",
            resolution_note="No defect found. Funds completed.",
        )
        
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, "completed")

    def test_close_dispute_transitions_to_completed(self):
        dispute = DisputeService.create_dispute(
            transaction_id=self.transaction.id,
            user=self.buyer,
            reason=DisputeReason.NOT_AS_DESCRIBED,
            description="Item is damaged",
        )
        
        staff_user = User.objects.create_superuser(
            email="staff@test.com", password="staffpass123"
        )
        
        # Close dispute
        DisputeService.resolve_dispute(
            dispute_id=dispute.id,
            resolver_user=staff_user,
            status="closed",
            resolution_note="Closed by mutual agreement",
        )
        
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, "completed")
