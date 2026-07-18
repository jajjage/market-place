from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.categories.models import Category
from apps.products.models import Product, ProductCondition
from apps.transactions.models import EscrowTransaction, FundHold, SellerBalanceLedger
from apps.transactions.services.escrow_services import EscrowTransactionService
from apps.transactions.services.ledger_service import SellerBalanceService
from apps.disputes.models import Dispute, DisputeStatus

User = get_user_model()


@pytest.mark.django_db
class TestEscrowHoldsAndLedger:

    @pytest.fixture(autouse=True)
    def setup_data(self):
        # Create users
        self.buyer = User.objects.create_user(
            email="buyer@test.com", password="testpass123", first_name="Buyer"
        )
        self.seller = User.objects.create_user(
            email="seller@test.com", password="testpass123", first_name="Seller"
        )
        self.staff_user = User.objects.create_user(
            email="admin@test.com", password="adminpass123", is_staff=True
        )

        # Create product setup
        self.condition = ProductCondition.objects.create(name="New", slug="new")
        self.category = Category.objects.create(name="Electronics", slug="elec")
        
        self.product = Product.objects.create(
            title="Test Widget",
            seller=self.seller,
            condition=self.condition,
            category=self.category,
            price=200.00,
        )

        self.transaction = EscrowTransaction.objects.create(
            product=self.product,
            buyer=self.buyer,
            seller=self.seller,
            tracking_id="TEST-TX-100",
            price=200.00,
            total_amount=200.00,
            status=EscrowTransaction.STATUS_INITIATED,
        )

    def test_payment_received_creates_active_hold(self):
        # Transition to payment_received
        EscrowTransactionService._update_escrow_transaction_status(
            escrow_transaction=self.transaction,
            new_status=EscrowTransaction.STATUS_PAYMENT_RECEIVED,
            user=self.staff_user,
        )

        # Verify hold creation
        assert FundHold.objects.filter(transaction=self.transaction).exists()
        hold = FundHold.objects.get(transaction=self.transaction)
        assert hold.status == FundHold.STATUS_ACTIVE
        assert hold.hold_type == FundHold.HOLD_TYPE_TRANSACTION
        assert hold.amount == Decimal("200.00")
        assert hold.seller == self.seller

    def test_completion_releases_hold_and_credits_seller(self):
        # Start payment
        EscrowTransactionService._update_escrow_transaction_status(
            escrow_transaction=self.transaction,
            new_status=EscrowTransaction.STATUS_PAYMENT_RECEIVED,
            user=self.staff_user,
        )
        
        # Complete transaction
        EscrowTransactionService._update_escrow_transaction_status(
            escrow_transaction=self.transaction,
            new_status=EscrowTransaction.STATUS_COMPLETED,
            user=self.staff_user,
        )

        # Verify hold is released
        hold = FundHold.objects.get(transaction=self.transaction)
        assert hold.status == FundHold.STATUS_RELEASED
        assert hold.released_at is not None

        # Verify ledger credit and fee
        credit_entry = SellerBalanceLedger.objects.get(
            transaction=self.transaction, entry_type=SellerBalanceLedger.ENTRY_SALE_CREDIT
        )
        assert credit_entry.amount == Decimal("200.00")

        fee_entry = SellerBalanceLedger.objects.get(
            transaction=self.transaction, entry_type=SellerBalanceLedger.ENTRY_PLATFORM_FEE
        )
        # Platform fee default is 5% = 10.00 NGN
        assert fee_entry.amount == Decimal("-10.00")

        # Verify total running balance
        running_balance = SellerBalanceService.get_running_balance(self.seller.id)
        assert running_balance == Decimal("190.00")
        assert not SellerBalanceService.is_balance_negative(self.seller.id)

    def test_dispute_transitions_hold_type(self):
        EscrowTransactionService._update_escrow_transaction_status(
            escrow_transaction=self.transaction,
            new_status=EscrowTransaction.STATUS_PAYMENT_RECEIVED,
            user=self.staff_user,
        )
        
        # Transition to disputed
        EscrowTransactionService._update_escrow_transaction_status(
            escrow_transaction=self.transaction,
            new_status=EscrowTransaction.STATUS_DISPUTED,
            user=self.staff_user,
        )

        hold = FundHold.objects.get(transaction=self.transaction)
        assert hold.status == FundHold.STATUS_ACTIVE
        assert hold.hold_type == FundHold.HOLD_TYPE_DISPUTE

    def test_refund_voids_active_holds(self):
        EscrowTransactionService._update_escrow_transaction_status(
            escrow_transaction=self.transaction,
            new_status=EscrowTransaction.STATUS_PAYMENT_RECEIVED,
            user=self.staff_user,
        )
        
        # Transition to refunded
        EscrowTransactionService._update_escrow_transaction_status(
            escrow_transaction=self.transaction,
            new_status=EscrowTransaction.STATUS_REFUNDED,
            user=self.staff_user,
        )

        hold = FundHold.objects.get(transaction=self.transaction)
        assert hold.status == FundHold.STATUS_VOIDED
        assert hold.released_at is not None

        # Verify no credits were recorded
        assert not SellerBalanceLedger.objects.filter(
            transaction=self.transaction, entry_type=SellerBalanceLedger.ENTRY_SALE_CREDIT
        ).exists()

    def test_register_late_chargeback_debits_ledger_and_opens_dispute(self):
        # 1. Simulate completed transaction
        EscrowTransactionService._update_escrow_transaction_status(
            escrow_transaction=self.transaction,
            new_status=EscrowTransaction.STATUS_PAYMENT_RECEIVED,
            user=self.staff_user,
        )
        EscrowTransactionService._update_escrow_transaction_status(
            escrow_transaction=self.transaction,
            new_status=EscrowTransaction.STATUS_COMPLETED,
            user=self.staff_user,
        )

        # Confirm initial running balance is positive
        assert SellerBalanceService.get_running_balance(self.seller.id) == Decimal("190.00")

        # 2. Trigger late chargeback
        dispute = EscrowTransactionService.register_late_chargeback(
            transaction_id=self.transaction.id,
            reason="Unrecognized card charge request"
        )

        # 3. Assertions
        assert dispute.status == DisputeStatus.OPENED
        self.transaction.refresh_from_db()
        assert self.transaction.status == EscrowTransaction.STATUS_DISPUTED

        # Verify chargeback debit ledger entry
        debit_entry = SellerBalanceLedger.objects.get(
            transaction=self.transaction, entry_type=SellerBalanceLedger.ENTRY_CHARGEBACK_DEBIT
        )
        assert debit_entry.amount == Decimal("-200.00")

        # Running balance should now be negative (190.00 - 200.00 = -10.00)
        running_balance = SellerBalanceService.get_running_balance(self.seller.id)
        assert running_balance == Decimal("-10.00")
        assert SellerBalanceService.is_balance_negative(self.seller.id)
