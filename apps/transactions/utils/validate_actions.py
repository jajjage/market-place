def requires_other_party_action(transaction):
    """Check if current status requires action from the other party"""
    status_requiring_other_party = {
        "payment_received": "seller",  # Seller needs to ship
        "shipped": "buyer",  # Buyer needs to confirm delivery
        "delivered": "buyer",  # Buyer needs to start inspection
        "completed": "seller",  # Seller needs to release funds
    }

    return transaction.status in status_requiring_other_party


def get_time_remaining(end_date):
    """Calculate time remaining until a deadline"""
    from django.utils import timezone

    if not end_date:
        return None

    now = timezone.now()
    if end_date <= now:
        return "expired"

    diff = end_date - now
    days = diff.days
    hours = diff.seconds // 3600

    if days > 0:
        return f"{days} days, {hours} hours"
    else:
        return f"{hours} hours"


def get_status_metadata(transaction):
    """Get additional metadata about the current status"""
    metadata = {
        "status_display": (
            transaction.get_status_display()
            if hasattr(transaction, "get_status_display")
            else transaction.status
        ),
        "is_final_status": transaction.status
        in ["completed", "funds_released", "cancelled", "refunded"],
        "requires_other_party_action": requires_other_party_action(transaction),
    }

    # Add time-sensitive information
    if transaction.status == "inspection" and hasattr(
        transaction, "inspection_end_date"
    ):
        metadata["inspection_end_date"] = transaction.inspection_end_date.isoformat()
        metadata["inspection_time_remaining"] = get_time_remaining(
            transaction.inspection_end_date
        )

    return metadata


def get_other_party_info(transaction, current_user):
    """Get information about the other party in the transaction"""
    if current_user == transaction.buyer:
        other_party = transaction.seller
        role = "seller"
    elif current_user == transaction.seller:
        other_party = transaction.buyer
        role = "buyer"
    else:
        return None

    return {
        "id": other_party.id if other_party else None,
        "username": other_party.username if other_party else None,
        "role": role,
    }


def get_required_fields_for_status(status):
    """Get list of required fields for a specific status"""
    required_fields = {
        "shipped": ["tracking_number", "shipping_carrier"],
        "disputed": ["notes"],  # Usually want notes for disputes
    }

    return required_fields.get(status, [])


def get_action_warnings(transaction, proposed_status):
    """Get warnings for potentially irreversible or important actions"""
    warnings = []

    if proposed_status == "disputed":
        warnings.append("Opening a dispute will require admin intervention to resolve")

    if proposed_status == "completed":
        warnings.append("Completing the transaction will release funds to the seller")

    if proposed_status == "cancelled":
        warnings.append("Cancelling the transaction cannot be undone")

    return warnings
