ESCROW_STATUSES = {
    "initiated": {
        "description": "Transaction created, awaiting payment",
        "auto_transitions": [],
        "final": False,
    },
    "payment_received": {
        "description": "Payment received, awaiting shipment",
        "auto_transitions": [],
        "final": False,
    },
    "shipped": {
        "description": "Item shipped, awaiting delivery confirmation",
        "auto_transitions": [],
        "final": False,
    },
    "delivered": {
        "description": "Delivery confirmed, grace period for inspection",
        "auto_transitions": [
            {"to": "inspection", "after_days": 3, "reason": "Grace period expired"}
        ],
        "final": False,
    },
    "inspection": {
        "description": "Under buyer inspection",
        "auto_transitions": [
            {
                "to": "completed",
                "dynamic_days": "inspection_period_days",
                "reason": "Inspection period expired",
            }
        ],
        "final": False,
    },
    "disputed": {
        "description": "Dispute filed, awaiting resolution",
        "auto_transitions": [],
        "final": False,
    },
    "completed": {
        "description": "Transaction completed successfully",
        "auto_transitions": [],
        "final": True,
    },
    "refunded": {
        "description": "Transaction refunded to buyer",
        "auto_transitions": [],
        "final": True,
    },
    "funds_released": {
        "description": "Fund release after successful Transaction",
        "auto_transitions": [],
        "final": True,
    },
    "cancelled": {
        "description": "Transaction cancelled",
        "auto_transitions": [],
        "final": True,
    },
}


def is_status_change_allowed(transaction, new_status, user):
    """
    Helper method to determine if a status change is allowed.
    Different roles can perform different status changes.
    """
    if user.is_staff:
        return True

    user_type = getattr(user, "user_type", None)

    is_buyer = user == transaction.buyer
    is_seller = user == transaction.seller

    allowed_transitions = {
        "BUYER": {
            "initiated": ["cancelled"] if is_buyer else [],
            "payment_received": [] if is_buyer else [],
            "shipped": ["delivered"] if is_buyer else [],
            "delivered": ["inspection"] if is_buyer else [],
            "inspection": ["completed", "disputed"] if is_buyer else [],
            "disputed": [] if is_buyer else [],
            "completed": [] if is_buyer else [],
            "refunded": [] if is_buyer else [],
            "cancelled": [] if is_buyer else [],
        },
        "SELLER": {
            "initiated": ["cancelled"] if is_seller else [],
            "payment_received": ["shipped"] if is_seller else [],
            "shipped": [] if is_seller else [],
            "delivered": [] if is_seller else [],
            "inspection": [] if is_seller else [],
            "disputed": [] if is_seller else [],
            "completed": ["funds_released"] if is_seller else [],
            "refunded": [] if is_seller else [],
            "cancelled": [] if is_seller else [],
        },
    }

    if user_type not in allowed_transitions:
        return False

    if transaction.status not in allowed_transitions[user_type]:
        return False

    return new_status in allowed_transitions[user_type][transaction.status]
