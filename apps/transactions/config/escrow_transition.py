from importlib import import_module
from django.conf import settings


class EscrowTransitionConfig:
    """Configuration for escrow transition timeouts"""

    DELIVERY_GRACE_PERIOD = getattr(settings, "DELIVERY_GRACE_PERIOD_DAYS", 3)
    INSPECTION_PERIOD = getattr(settings, "INSPECTION_PERIOD_DAYS", 7)
    DISPUTE_AUTO_REFUND = getattr(settings, "DISPUTE_AUTO_REFUND_DAYS", 14)
    SHIPPING_TIMEOUT = getattr(settings, "SHIPPING_TIMEOUT_DAYS", 5)

    TIMEOUT_CONFIGS = {
        "delivered": {
            "timeout_type": "inspection_start",
            "to_status": "inspection",
            "days": DELIVERY_GRACE_PERIOD,
            "task": "apps.transactions.tasks.transitions_tasks.schedule_auto_inspection",
        },
        "inspection": {
            "timeout_type": "inspection_end",
            "to_status": "completed",
            "days": INSPECTION_PERIOD,
            "task": "apps.transactions.tasks.transitions_tasks.schedule_auto_completion",
        },
        "disputed": {
            "timeout_type": "dispute_refund",
            "to_status": "refunded",
            "days": DISPUTE_AUTO_REFUND,
            "task": "apps.transactions.tasks.transitions_tasks.auto_refund_disputed_transaction",
        },
        "payment_received": {
            "timeout_type": "shipping",
            "to_status": "shipped",
            "days": SHIPPING_TIMEOUT,
            "task": "apps.transactions.tasks.transitions_tasks.schedule_shipping_timeout",
        },
    }

    @classmethod
    def get_timeout_config(cls, status: str):
        return cls.TIMEOUT_CONFIGS.get(status)

    @staticmethod
    def _resolve_task(task_path: str):
        module_path, func_name = task_path.rsplit(".", 1)
        module = import_module(module_path)
        return getattr(module, func_name)
