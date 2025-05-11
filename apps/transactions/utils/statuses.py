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
