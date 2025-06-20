# services/inventory.py
from django.db import transaction

# from django.utils import timezone
# from datetime import timedelta

from apps.transactions.models import EscrowTransaction, TransactionHistory
from apps.transactions.utils.tracking_id import generate_tracking_id
from .models import (
    InventoryTransaction,
)


class InventoryService:
    """Service for managing product inventory lifecycle"""

    @staticmethod
    @transaction.atomic
    def add_inventory(product, quantity, user=None, notes=""):
        """
        Add inventory to total quantity

        Args:
            product: The product to add inventory to
            quantity: The quantity to add
            user: The user performing the action
            notes: Additional notes about the transaction

        Returns:
            The updated product object or None if operation failed
        """
        if quantity <= 0:
            return None

        # Record previous values
        prev_total = product.total_inventory
        prev_available = product.available_inventory
        prev_in_escrow = product.in_escrow_inventory

        # Update inventory
        product.total_inventory += quantity
        product.save(update_fields=["total_inventory"])

        # Create transaction record
        InventoryTransaction.objects.create(
            product=product,
            transaction_type="ADD",
            quantity=quantity,
            previous_total=prev_total,
            previous_available=prev_available,
            previous_in_escrow=prev_in_escrow,
            new_total=product.total_inventory,
            new_available=product.available_inventory,
            new_in_escrow=product.in_escrow_inventory,
            created_by=user,
            notes=notes,
        )

        return product

    @staticmethod
    @transaction.atomic
    def activate_inventory(product, quantity=None, user=None, notes=""):
        """
        Move inventory from total to available

        Args:
            product: The product to activate inventory for
            quantity: The quantity to activate (None = activate all)
            user: The user performing the action
            notes: Additional notes about the transaction

        Returns:
            The updated product object or None if nothing was activated
        """
        # Calculate how much is available to activate
        activatable = (
            product.total_inventory
            - product.available_inventory
            - product.in_escrow_inventory
        )

        if quantity is None:
            # Activate all available inventory
            quantity = activatable
        else:
            # Make sure we don't activate more than possible
            quantity = min(quantity, activatable)

        if quantity <= 0:
            return None  # Nothing to activate

        # Record previous values
        prev_total = product.total_inventory
        prev_available = product.available_inventory
        prev_in_escrow = product.in_escrow_inventory

        # Update inventory
        product.available_inventory += quantity
        product.save(update_fields=["available_inventory"])

        # Create transaction record
        InventoryTransaction.objects.create(
            product=product,
            transaction_type="ACTIVATE",
            quantity=quantity,
            previous_total=prev_total,
            previous_available=prev_available,
            previous_in_escrow=prev_in_escrow,
            new_total=product.total_inventory,
            new_available=product.available_inventory,
            new_in_escrow=product.in_escrow_inventory,
            created_by=user,
            notes=notes,
        )

        return product

    @staticmethod
    @transaction.atomic
    def place_in_escrow(
        product,
        quantity=1,
        buyer=None,
        seller=None,
        price=0,
        currency="USD",
        inspection_period_days=3,
        shipping_address=None,
        user=None,
        notes="",
    ):
        """
        Move inventory from available to escrow and create escrow transaction

        Args:
            product: The product to place in escrow
            quantity: The quantity to place in escrow
            buyer: The user buying the product
            seller: The user selling the product
            amount: The transaction amount
            currency: The transaction currency
            inspection_period_days: Days for inspection period
            shipping_address: Address for shipping
            user: The user performing the action
            notes: Additional notes about the transaction

        Returns:
            Tuple of (updated product, escrow transaction) or (None, None) if failed
        """
        # Check if enough available
        if product.available_inventory < quantity:
            return None, None  # Not enough available

        # Record previous values
        prev_total = product.total_inventory
        prev_available = product.available_inventory
        prev_in_escrow = product.in_escrow_inventory

        # Update inventory
        product.available_inventory -= quantity
        product.in_escrow_inventory += quantity
        product.save(update_fields=["available_inventory", "in_escrow_inventory"])
        amount_paid = price
        if quantity > 1:
            amount_paid = price * quantity

        seller = product.seller
        # Create inventory transaction record
        InventoryTransaction.objects.create(
            product=product,
            transaction_type="ESCROW",
            quantity=quantity,
            previous_total=prev_total,
            previous_available=prev_available,
            previous_in_escrow=prev_in_escrow,
            new_total=product.total_inventory,
            new_available=product.available_inventory,
            new_in_escrow=product.in_escrow_inventory,
            created_by=user,
            notes=notes,
        )

        # Create escrow transaction
        escrow_transaction = EscrowTransaction.objects.create(
            product=product,
            buyer=buyer,
            seller=seller,
            quantity=quantity,
            currency=currency,
            status="initiated",
            inspection_period_days=inspection_period_days,
            price=price,
            shipping_address=shipping_address,
            tracking_id=generate_tracking_id(product, buyer, seller),
            notes=notes,
        )

        # Create transaction history record
        TransactionHistory.objects.create(
            transaction=escrow_transaction,
            new_status="initiated",
            notes=f"Escrow transaction initiated for {quantity} units of {product.title}",
            created_by=user,
        )

        return product, escrow_transaction, amount_paid

    @staticmethod
    @transaction.atomic
    def release_from_escrow(
        product,
        quantity=1,
        escrow_transaction=None,
        previous_status=None,
        release_type="return",
        user=None,
        notes="",
    ):
        """
        Release inventory from escrow

        Args:
            product: The product to release from escrow
            quantity: The quantity to release
            escrow_transaction: The associated escrow transaction
            release_type: Either "return" (to available) or "deduct" (from total)
            user: The user performing the action
            notes: Additional notes about the transaction

        Returns:
            The updated product object or None if failed
        """
        if product.in_escrow_inventory < quantity:
            return None  # Not enough in escrow

        # Record previous values
        prev_total = product.total_inventory
        prev_available = product.available_inventory
        prev_in_escrow = product.in_escrow_inventory

        # Update inventory based on release type
        product.in_escrow_inventory -= quantity

        if release_type == "return":
            # Return to available inventory
            product.available_inventory += quantity
            transaction_type = "RETURN_FROM_ESCROW"
            update_fields = ["available_inventory", "in_escrow_inventory"]
        else:
            # Deduct from total inventory (item sold)
            product.total_inventory -= quantity
            transaction_type = "COMPLETE_ESCROW"
            update_fields = ["total_inventory", "in_escrow_inventory"]

        product.save(update_fields=update_fields)

        # Create transaction record
        InventoryTransaction.objects.create(
            product=product,
            transaction_type=transaction_type,
            quantity=quantity,
            previous_total=prev_total,
            previous_available=prev_available,
            previous_in_escrow=prev_in_escrow,
            new_total=product.total_inventory,
            new_available=product.available_inventory,
            new_in_escrow=product.in_escrow_inventory,
            created_by=user,
            notes=notes,
        )

        # Update escrow transaction if provided
        if escrow_transaction:
            if release_type == "return":
                escrow_transaction.status = "cancelled"
                status_note = "Transaction cancelled, items returned to inventory"
            else:
                escrow_transaction.status = "completed"
                status_note = "Transaction completed, items removed from inventory"

            escrow_transaction.save(update_fields=["status"])

            # Create transaction history record
            TransactionHistory.objects.create(
                transaction=escrow_transaction,
                previous_status=previous_status,
                new_status=escrow_transaction.status,
                notes=status_note,
                created_by=user,
            )

        return product

    @staticmethod
    @transaction.atomic
    def deduct_inventory(product, quantity=1, user=None, notes=""):
        """
        Deduct inventory from available (for direct sales without escrow)

        Args:
            product: The product to deduct inventory from
            quantity: The quantity to deduct
            user: The user performing the action
            notes: Additional notes about the transaction

        Returns:
            The updated product object or None if failed
        """
        if product.available_inventory < quantity:
            return None  # Not enough available

        # Record previous values
        prev_total = product.total_inventory
        prev_available = product.available_inventory
        prev_in_escrow = product.in_escrow_inventory

        # Update inventory
        product.total_inventory -= quantity
        product.available_inventory -= quantity
        product.save(update_fields=["total_inventory", "available_inventory"])

        # Create transaction record
        InventoryTransaction.objects.create(
            product=product,
            transaction_type="DEDUCT",
            quantity=quantity,
            previous_total=prev_total,
            previous_available=prev_available,
            previous_in_escrow=prev_in_escrow,
            new_total=product.total_inventory,
            new_available=product.available_inventory,
            new_in_escrow=product.in_escrow_inventory,
            created_by=user,
            notes=notes,
        )

        return product
