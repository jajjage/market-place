import logging
from django.db.models import Sum
from django.db import transaction
from decimal import Decimal
from apps.transactions.models import SellerBalanceLedger
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)


class SellerBalanceService:
    """
    Service for calculating and querying seller running balances and ledger entries.
    """

    @classmethod
    def get_running_balance(cls, seller_id: int) -> Decimal:
        """
        Calculate the net balance of a seller by summing all ledger credit/debit entries.
        """
        result = SellerBalanceLedger.objects.filter(seller_id=seller_id).aggregate(
            total=Sum("amount")
        )
        return result["total"] or Decimal("0.00")

    @classmethod
    def is_balance_negative(cls, seller_id: int) -> bool:
        """
        Check if the seller has a net negative balance (e.g. from chargebacks).
        """
        return cls.get_running_balance(seller_id) < Decimal("0.00")

    @classmethod
    @transaction.atomic
    def record_entry(
        cls,
        seller,
        amount: Decimal,
        entry_type: str,
        transaction_obj=None,
        description: str = "",
    ) -> SellerBalanceLedger:
        """
        Record a credit or debit entry into the seller ledger.
        """
        entry = SellerBalanceLedger.objects.create(
            seller=seller,
            amount=amount,
            entry_type=entry_type,
            transaction=transaction_obj,
            description=description,
        )
        logger.info(
            f"Recorded ledger entry {entry.id} of type {entry_type} for seller {seller.id}: {amount}"
        )
        return entry
