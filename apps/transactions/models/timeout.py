# apps/transactions/models/timeout.py
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel


class EscrowTimeout(BaseModel):
    """
    Tracks scheduled automatic transitions for escrow transactions
    Replaces the need for timeout tracking fields in EscrowTransaction
    """

    TIMEOUT_TYPES = [
        ("shipping", "Shipping Timeout"),  # payment_received → shipped/cancelled
        ("inspection_start", "Auto Inspection"),  # delivered → inspection
        ("inspection_end", "Auto Completion"),  # inspection → completed
        ("dispute_refund", "Auto Refund"),  # disputed → refunded
    ]

    transaction = models.ForeignKey(
        "transactions.EscrowTransaction",
        on_delete=models.CASCADE,
        related_name="escrowtimeout",
    )
    timeout_type = models.CharField(
        max_length=20,
        choices=TIMEOUT_TYPES,
        help_text="Type of automatic transition being scheduled",
    )
    from_status = models.CharField(
        max_length=20,
        help_text="Status the transaction should be in when timeout executes",
    )
    to_status = models.CharField(
        max_length=20, help_text="Status to transition to when timeout expires"
    )

    # Timing fields
    scheduled_at = models.DateTimeField(
        default=timezone.now, help_text="When this timeout was scheduled"
    )
    expires_at = models.DateTimeField(
        help_text="When the automatic transition should occur"
    )

    # Task tracking
    celery_task_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="Celery task ID for cancellation purposes",
    )

    # Status tracking
    is_executed = models.BooleanField(
        default=False, help_text="Whether the timeout has been executed"
    )
    is_cancelled = models.BooleanField(
        default=False,
        help_text="Whether the timeout was cancelled (due to manual status change)",
    )
    execution_notes = models.TextField(
        blank=True, help_text="Notes about timeout execution or cancellation"
    )
    executed_at = models.DateTimeField(
        null=True, blank=True, help_text="When the timeout was actually executed"
    )

    class Meta:
        db_table = "escrow_timeouts"
        indexes = [
            models.Index(fields=["transaction", "timeout_type"]),
            models.Index(fields=["expires_at", "is_executed", "is_cancelled"]),
            models.Index(fields=["celery_task_id"]),
        ]
        # Ensure only one active timeout per transaction per type
        constraints = [
            models.UniqueConstraint(
                fields=["transaction", "timeout_type"],
                condition=models.Q(is_cancelled=False, is_executed=False),
                name="unique_active_timeout_per_type",
            )
        ]

    def __str__(self):
        return f"Timeout {self.timeout_type} for Transaction {self.transaction.id}"

    @property
    def is_active(self):
        """Check if timeout is still active (not executed or cancelled)"""
        return not self.is_executed and not self.is_cancelled

    @property
    def is_expired(self):
        """Check if timeout has passed its expiration time"""
        return timezone.now() >= self.expires_at

    def cancel(self, notes=""):
        """Cancel this timeout and its associated Celery task"""
        from celery import current_app

        if self.is_active:
            # Cancel the Celery task
            current_app.control.revoke(self.celery_task_id, terminate=True)

            # Mark as cancelled
            self.is_cancelled = True
            self.execution_notes = (
                notes or "Timeout cancelled due to manual status change"
            )
            self.executed_at = timezone.now()
            self.save(update_fields=["is_cancelled", "execution_notes", "executed_at"])

    def execute(self, notes=""):
        """Mark timeout as executed"""
        if self.is_active:
            self.is_executed = True
            self.execution_notes = notes
            self.executed_at = timezone.now()
            self.save(update_fields=["is_executed", "execution_notes", "executed_at"])

    @classmethod
    def cancel_active_timeouts_for_transaction(cls, transaction_id, timeout_type=None):
        """Cancel all active timeouts for a transaction, optionally filtered by type"""
        filters = {
            "transaction_id": transaction_id,
            "is_cancelled": False,
            "is_executed": False,
        }

        if timeout_type:
            filters["timeout_type"] = timeout_type

        active_timeouts = cls.objects.filter(**filters)

        for timeout in active_timeouts:
            timeout.cancel("Cancelled due to transaction status change")

        return active_timeouts.count()

    @classmethod
    def get_active_timeout(cls, transaction_id, timeout_type):
        """Get active timeout for a specific transaction and type"""
        try:
            return cls.objects.get(
                transaction_id=transaction_id,
                timeout_type=timeout_type,
                is_cancelled=False,
                is_executed=False,
            )
        except cls.DoesNotExist:
            return None
