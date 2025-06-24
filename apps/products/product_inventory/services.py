from decimal import Decimal
from typing import List, Dict, Tuple
from django.db import transaction
from django.core.exceptions import ValidationError

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
    def add_inventory(variant, quantity, user=None, notes=""):
        """
        Add inventory to total quantity

        Args:
            variant: The variant to add inventory to
            quantity: The quantity to add
            user: The user performing the action
            notes: Additional notes about the transaction

        Returns:
            The updated variant object or None if operation failed
        """
        if quantity <= 0:
            return None

        # Record previous values
        prev_total = variant.total_inventory
        prev_available = variant.available_inventory
        prev_in_escrow = variant.in_escrow_inventory

        # Update inventory
        variant.total_inventory += quantity
        variant.save(update_fields=["total_inventory"])

        # Create transaction record
        InventoryTransaction.objects.create(
            product=variant.product,
            variant=variant,
            transaction_type="ADD",
            quantity=quantity,
            previous_total=prev_total,
            previous_available=prev_available,
            previous_in_escrow=prev_in_escrow,
            new_total=variant.total_inventory,
            new_available=variant.available_inventory,
            new_in_escrow=variant.in_escrow_inventory,
            created_by=user,
            notes=notes,
        )

        return variant

    @staticmethod
    @transaction.atomic
    def activate_inventory(variant, quantity=None, user=None, notes=""):
        """
        Move inventory from total to available

        Args:
            variant: The variant to activate inventory for
            quantity: The quantity to activate (None = activate all)
            user: The user performing the action
            notes: Additional notes about the transaction

        Returns:
            The updated variant object or None if nothing was activated
        """
        # Calculate how much is available to activate
        activatable = (
            variant.total_inventory
            - variant.available_inventory
            - variant.in_escrow_inventory
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
        prev_total = variant.total_inventory
        prev_available = variant.available_inventory
        prev_in_escrow = variant.in_escrow_inventory

        # Update inventory
        variant.available_inventory += quantity
        variant.save(update_fields=["available_inventory"])

        # Create transaction record
        InventoryTransaction.objects.create(
            product=variant.product,
            variant=variant,
            transaction_type="ACTIVATE",
            quantity=quantity,
            previous_total=prev_total,
            previous_available=prev_available,
            previous_in_escrow=prev_in_escrow,
            new_total=variant.total_inventory,
            new_available=variant.available_inventory,
            new_in_escrow=variant.in_escrow_inventory,
            created_by=user,
            notes=notes,
        )

        return variant

    @staticmethod
    @transaction.atomic
    def place_in_escrow(
        variant,  # ProductVariant instance
        quantity: int = 1,
        buyer=None,
        seller=None,
        negotiated_price: Decimal = None,  # renamed for clarity
        currency: str = "USD",
        inspection_period_days: int = 3,
        shipping_address=None,
        user=None,
        notes: str = "",
    ):
        """
        Reserve stock on a specific variant, then create an escrow transaction.
        Uses the variant's final_price (which includes option adjustments) unless
        a negotiated_price is provided.
        """
        # 1) Inventory check on the variant level
        if not variant.is_active:
            raise ValidationError(f"Variant {variant.sku} is not active")

        if variant.available_quantity < quantity:
            raise ValidationError(
                f"Insufficient stock for variant {variant.sku}. "
                f"Available: {variant.available_quantity}, Requested: {quantity}"
            )

        # 2) Calculate the unit price
        # Use the variant's final_price property which includes option adjustments
        base_unit_price = variant.final_price

        if base_unit_price is None:
            raise ValidationError(f"No price set for variant {variant.sku}")

        # 3) Handle negotiated price if provided
        if negotiated_price is not None:
            # Ensure negotiation didn't exceed the calculated price
            if negotiated_price > base_unit_price:
                raise ValidationError(
                    f"Negotiated price ({negotiated_price}) cannot exceed "
                    f"list price ({base_unit_price})"
                )
            unit_price = negotiated_price
        else:
            unit_price = base_unit_price

        # 4) Compute total amount
        total_amount = unit_price * quantity

        # 5) Reserve the stock using the variant's method
        if not variant.reserve_stock(quantity):
            raise ValidationError(f"Failed to reserve stock for variant {variant.sku}")

        try:
            # 6) Record the inventory movement
            InventoryTransaction.objects.create(
                product=variant.product,
                variant=variant,
                transaction_type="ESCROW",
                quantity=quantity,
                previous_available=variant.available_inventory
                + quantity,  # before reservation
                previous_in_escrow=variant.in_escrow_inventory
                - quantity,  # before reservation
                new_available=variant.available_inventory,
                new_in_escrow=variant.in_escrow_inventory,
                created_by=user,
                notes=f"Reserved for escrow: {notes}",
            )

            # 7) Create the escrow transaction
            escrow_tx = EscrowTransaction.objects.create(
                product=variant.product,
                variant=variant,
                buyer=buyer,
                seller=seller or variant.product.seller,
                quantity=quantity,
                currency=currency,
                status="initiated",
                inspection_period_days=inspection_period_days,
                unit_price=unit_price,
                total_amount=total_amount,
                shipping_address=shipping_address,
                tracking_id=generate_tracking_id(variant, buyer, seller),
                notes=notes,
            )

            # 8) History record
            TransactionHistory.objects.create(
                transaction=escrow_tx,
                new_status="initiated",
                notes=(
                    f"Escrow initiated for {quantity}× "
                    f"{variant.product.title} - {variant.sku} "
                    f"at {unit_price} each (Total: {total_amount})"
                ),
                created_by=user,
            )

            return variant, escrow_tx, total_amount

        except Exception as e:
            # If escrow creation fails, release the reserved stock
            variant.release_stock(quantity)
            raise e

    @staticmethod
    @transaction.atomic
    def place_multiple_variants_in_escrow(
        variant_orders: List[
            Dict
        ],  # [{'variant': variant_obj, 'quantity': 2, 'negotiated_price': None}, ...]
        buyer=None,
        seller=None,
        currency: str = "USD",
        inspection_period_days: int = 3,
        shipping_address=None,
        user=None,
        notes: str = "",
    ) -> Tuple[List[Dict], Decimal]:
        """
        Handle multiple variant purchases in a single escrow transaction.

        Args:
            variant_orders: List of dicts with 'variant', 'quantity', and optional 'negotiated_price'

        Returns:
            Tuple of (successful_orders, total_amount)
        """
        successful_orders = []
        total_amount = Decimal("0.00")
        failed_orders = []

        # First pass: validate all variants and calculate total
        for order in variant_orders:
            variant = order["variant"]
            quantity = order["quantity"]
            negotiated_price = order.get("negotiated_price")

            try:
                # Check availability
                if not variant.is_active:
                    failed_orders.append(
                        {
                            "variant": variant,
                            "error": f"Variant {variant.sku} is not active",
                        }
                    )
                    continue

                if variant.available_quantity < quantity:
                    failed_orders.append(
                        {
                            "variant": variant,
                            "error": f"Insufficient stock for {variant.sku}",
                        }
                    )
                    continue

                # Calculate price
                base_price = variant.final_price
                if base_price is None:
                    failed_orders.append(
                        {"variant": variant, "error": f"No price set for {variant.sku}"}
                    )
                    continue

                unit_price = (
                    negotiated_price if negotiated_price is not None else base_price
                )

                if negotiated_price and negotiated_price > base_price:
                    failed_orders.append(
                        {
                            "variant": variant,
                            "error": f"Negotiated price exceeds list price for {variant.sku}",
                        }
                    )
                    continue

                order_total = unit_price * quantity
                total_amount += order_total

                successful_orders.append(
                    {
                        "variant": variant,
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "order_total": order_total,
                    }
                )

            except Exception as e:
                failed_orders.append({"variant": variant, "error": str(e)})

        # If any orders failed, raise an error with details
        if failed_orders:
            error_details = "; ".join(
                [f"{order['variant'].sku}: {order['error']}" for order in failed_orders]
            )
            raise ValidationError(
                f"Some variants could not be processed: {error_details}"
            )

        # Second pass: reserve stock and create transactions
        escrow_transactions = []
        reserved_variants = []  # Keep track for rollback if needed

        try:
            for order in successful_orders:
                variant = order["variant"]
                quantity = order["quantity"]

                # Reserve stock
                if not variant.reserve_stock(quantity):
                    raise ValidationError(f"Failed to reserve stock for {variant.sku}")

                reserved_variants.append({"variant": variant, "quantity": quantity})

                # Create escrow transaction for this variant
                escrow_tx = EscrowTransaction.objects.create(
                    product=variant.product,
                    variant=variant,
                    buyer=buyer,
                    seller=seller or variant.product.seller,
                    quantity=quantity,
                    currency=currency,
                    status="initiated",
                    inspection_period_days=inspection_period_days,
                    unit_price=order["unit_price"],
                    total_amount=order["order_total"],
                    shipping_address=shipping_address,
                    tracking_id=generate_tracking_id(variant, buyer, seller),
                    notes=f"Multi-variant order: {notes}",
                )

                escrow_transactions.append(escrow_tx)

                # Create history record
                TransactionHistory.objects.create(
                    transaction=escrow_tx,
                    new_status="initiated",
                    notes=(
                        f"Multi-variant escrow: {quantity}× {variant.sku} "
                        f"at {order['unit_price']} each"
                    ),
                    created_by=user,
                )

            return successful_orders, total_amount

        except Exception as e:
            # Rollback: release all reserved stock
            for reserved in reserved_variants:
                reserved["variant"].release_stock(reserved["quantity"])
            raise e

    @staticmethod
    @transaction.atomic
    def release_from_escrow(
        variant,
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
        if variant.in_escrow_inventory < quantity:
            return None  # Not enough in escrow

        # Record previous values
        prev_total = variant.total_inventory
        prev_available = variant.available_inventory
        prev_in_escrow = variant.in_escrow_inventory

        # Update inventory based on release type
        variant.in_escrow_inventory -= quantity

        if release_type == "return":
            # Return to available inventory
            variant.available_inventory += quantity
            transaction_type = "RETURN_FROM_ESCROW"
            update_fields = ["available_inventory", "in_escrow_inventory"]
        else:
            # Deduct from total inventory (item sold)
            variant.total_inventory -= quantity
            transaction_type = "COMPLETE_ESCROW"
            update_fields = ["total_inventory", "in_escrow_inventory"]

        variant.save(update_fields=update_fields)

        # Create transaction record
        InventoryTransaction.objects.create(
            product=variant.product,
            variant=variant,
            transaction_type=transaction_type,
            quantity=quantity,
            previous_total=prev_total,
            previous_available=prev_available,
            previous_in_escrow=prev_in_escrow,
            new_total=variant.total_inventory,
            new_available=variant.available_inventory,
            new_in_escrow=variant.in_escrow_inventory,
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

        return variant.product

    @staticmethod
    @transaction.atomic
    def deduct_inventory(variant, quantity=1, user=None, notes=""):
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
        if variant.available_inventory < quantity:
            return None  # Not enough available

        # Record previous values
        prev_total = variant.total_inventory
        prev_available = variant.available_inventory
        prev_in_escrow = variant.in_escrow_inventory

        # Update inventory
        variant.total_inventory -= quantity
        variant.available_inventory -= quantity
        variant.save(update_fields=["total_inventory", "available_inventory"])

        # Create transaction record
        InventoryTransaction.objects.create(
            product=variant.product,
            variant=variant,
            transaction_type="DEDUCT",
            quantity=quantity,
            previous_total=prev_total,
            previous_available=prev_available,
            previous_in_escrow=prev_in_escrow,
            new_total=variant.total_inventory,
            new_available=variant.available_inventory,
            new_in_escrow=variant.in_escrow_inventory,
            created_by=user,
            notes=notes,
        )

        return variant.product
