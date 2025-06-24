from django.shortcuts import get_object_or_404
from rest_framework import status

from apps.core.utils.cache_manager import CacheManager
from apps.products.product_negotiation.models import PriceNegotiation


def get_transaction_context(user, negotiation_id, variant):
    """
    Determine the context of the transaction (direct vs negotiation-based).
    Returns a context dict with negotiation info and pricing.
    """
    context = {
        "negotiation": None,
        "price": None,  # Will use variant's default price if None
        "is_negotiated": False,
        "original_price": variant.final_price,
    }

    if negotiation_id:
        try:
            negotiation = get_object_or_404(
                PriceNegotiation.objects.select_related("product", "buyer", "seller"),
                id=negotiation_id,
            )
            context.update(
                {
                    "negotiation": negotiation,
                    "price": negotiation.final_price,
                    "is_negotiated": True,
                }
            )
        except Exception:
            # If negotiation not found, we'll handle this in validation
            context["negotiation"] = "not_found"

    return context


def validate_transaction_context(user, context, quantity):
    """
    Validate the transaction context and user permissions.
    Returns dict with error info or success status.
    """
    # Handle negotiation validation
    if context.get("negotiation") == "not_found":
        return {
            "error": True,
            "message": "Negotiation not found",
            "status_code": status.HTTP_404_NOT_FOUND,
        }

    if context["negotiation"]:
        negotiation = context["negotiation"]

        # Check permissions
        if user != negotiation.buyer:
            return {
                "error": True,
                "message": "Only the buyer can create a transaction from this negotiation",
                "status_code": status.HTTP_403_FORBIDDEN,
            }

        # Check negotiation status
        if negotiation.status != "accepted":
            return {
                "error": True,
                "message": f"Cannot create transaction for negotiation with status '{negotiation.status}'",
                "status_code": status.HTTP_400_BAD_REQUEST,
            }

        # Check if transaction already exists
        if negotiation.transaction:
            return {
                "error": True,
                "message": "A transaction already exists for this negotiation",
                "status_code": status.HTTP_400_BAD_REQUEST,
            }

    return {"error": False}


def link_negotiation_to_transaction(negotiation, escrow_transaction):
    """Link the negotiation to the created transaction."""
    negotiation.transaction = escrow_transaction
    negotiation.save(update_fields=["transaction"])


def invalidate_caches(product, negotiation=None):
    """Invalidate relevant caches."""
    if negotiation:
        CacheManager.invalidate("negotiation", "detail", id=negotiation.id)


def prepare_response_data(variant, escrow_transaction, amount_paid, quantity, context):
    """Prepare the response data based on transaction context."""
    base_data = {
        "message": "Transaction created successfully",
        "transaction_id": escrow_transaction.id,
        "tracking_id": escrow_transaction.tracking_id,
        "product": {
            "id": variant.product.id,
            "name": variant.product.title,
        },
        "variant": {
            "id": variant.id,
            "sku": variant.sku,
        },
        "quantity": quantity,
        "total_amount": f"${float(amount_paid)}",
        "status": escrow_transaction.status,
        "inventory": {
            "total": variant.total_inventory,
            "available": variant.available_inventory,
            "in_escrow": variant.in_escrow_inventory,
        },
    }

    # Add negotiation-specific data if applicable
    if context["is_negotiated"]:
        negotiation = context["negotiation"]
        original_price = context["original_price"]
        negotiated_price = context["price"]

        savings_per_item = original_price - negotiated_price
        total_savings = savings_per_item * quantity

        base_data.update(
            {
                "message": "Transaction created successfully from negotiation",
                "negotiation_id": negotiation.id,
                "pricing": {
                    "original_price": f"${float(original_price)}",
                    "negotiated_price": f"${float(negotiated_price)}",
                    "savings_per_item": f"${float(savings_per_item)}",
                    "total_savings": f"${float(total_savings)}",
                },
            }
        )

    return base_data
