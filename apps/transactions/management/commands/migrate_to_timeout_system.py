# apps/transactions/management/commands/migrate_to_timeout_system.py
from django.core.management.base import BaseCommand
from django.db import transaction, models
from django.utils import timezone
from datetime import timedelta

from apps.transactions.models import (
    EscrowTransaction,
    EscrowTimeout,
    TransactionHistory,
)
from apps.transactions.services.transition_service import EscrowTransitionConfig


class Command(BaseCommand):
    help = "Migrate existing transactions to use the new timeout tracking system (cron-friendly)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without actually doing it",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force migration even if timeouts already exist",
        )
        parser.add_argument(
            "--status",
            type=str,
            help="Only migrate transactions with this specific status",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress non-error output (useful for cron jobs)",
        )
        parser.add_argument(
            "--max-age-hours",
            type=int,
            default=24,
            help="Only process transactions modified within this many hours (default: 24)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Process transactions in batches of this size (default: 100)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]
        specific_status = options["status"]
        quiet = options["quiet"]
        max_age_hours = options["max_age_hours"]
        batch_size = options["batch_size"]

        # Configure output based on quiet mode
        if quiet:
            self.stdout = (
                open("/dev/null", "w") if hasattr(self, "stdout") else self.stdout
            )

        if dry_run and not quiet:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        # Find transactions that need timeout scheduling
        transactions_to_migrate = self._find_transactions_needing_timeouts(
            force, specific_status, max_age_hours
        )

        if not transactions_to_migrate:
            if not quiet:
                self.stdout.write(self.style.SUCCESS("No transactions need migration"))
            return

        if not quiet:
            self.stdout.write(
                f"Found {len(transactions_to_migrate)} transactions to migrate"
            )

        # Process in batches for better performance and memory usage
        migrated_count = 0
        skipped_count = 0
        error_count = 0

        for i in range(0, len(transactions_to_migrate), batch_size):
            batch = transactions_to_migrate[i : i + batch_size]

            if not quiet:
                self.stdout.write(
                    f"Processing batch {i // batch_size + 1} ({len(batch)} transactions)"
                )

            for txn in batch:
                try:
                    if self._migrate_transaction(txn, dry_run, quiet):
                        migrated_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    error_count += 1
                    # Always show errors even in quiet mode
                    self.stderr.write(f"Error migrating transaction {txn.id}: {str(e)}")

        # Summary - always show summary for cron job monitoring
        if not quiet or error_count > 0:
            self.stdout.write("\n" + "=" * 50)
            self.stdout.write("Migration Summary:")
            self.stdout.write(f"  Migrated: {migrated_count}")
            self.stdout.write(f"  Skipped: {skipped_count}")
            self.stdout.write(f"  Errors: {error_count}")

            if dry_run:
                self.stdout.write(
                    self.style.WARNING("DRY RUN - No actual changes were made")
                )
            else:
                self.stdout.write(self.style.SUCCESS("Migration completed"))

        # Return appropriate exit code for cron job monitoring
        if error_count > 0:
            exit(1)  # Non-zero exit code indicates errors

    def _find_transactions_needing_timeouts(
        self, force=False, specific_status=None, max_age_hours=24
    ):
        """Find transactions that should have timeouts but don't"""

        # Statuses that should have timeouts
        timeout_statuses = list(EscrowTransitionConfig.TIMEOUT_CONFIGS.keys())

        # Filter by specific status if provided
        if specific_status:
            if specific_status not in timeout_statuses:
                self.stdout.write(
                    self.style.ERROR(
                        f'Status "{specific_status}" does not have timeout configuration'
                    )
                )
                return []
            timeout_statuses = [specific_status]

        # Calculate the cutoff time for recent transactions
        cutoff_time = timezone.now() - timedelta(hours=max_age_hours)

        # Get recent transactions in these statuses
        candidates = (
            EscrowTransaction.objects.filter(
                status__in=timeout_statuses,
                updated_at__gte=cutoff_time,  # Only process recently updated transactions
            )
            .select_related()
            .order_by("id")
        )

        transactions_needing_timeouts = []

        for txn in candidates:
            # Check if transaction already has active timeouts
            has_active_timeout = EscrowTimeout.objects.filter(
                transaction=txn, is_executed=False, is_cancelled=False
            ).exists()

            if not has_active_timeout or force:
                transactions_needing_timeouts.append(txn)

        return transactions_needing_timeouts

    def _migrate_transaction(self, txn, dry_run=False, quiet=False):
        """Migrate a single transaction to the timeout system"""

        timeout_config = EscrowTransitionConfig.get_timeout_config(txn.status)
        if not timeout_config:
            if not quiet:
                self.stdout.write(
                    f"  No timeout config for status {txn.status} (Transaction {txn.id})"
                )
            return False

        # Calculate when the timeout should expire
        expires_at = self._calculate_expiration_time(txn, timeout_config)

        if expires_at is None:
            if not quiet:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Could not calculate expiration time for transaction {txn.id}, skipping"
                    )
                )
            return False

        if expires_at <= timezone.now():
            if not quiet:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Timeout already expired for transaction {txn.id} (would expire at {expires_at}), skipping"
                    )
                )
            return False

        if not quiet:
            self.stdout.write(
                f"  Migrating transaction {txn.id} ({txn.status}) - expires at {expires_at}"
            )

        if not dry_run:
            with transaction.atomic():
                # Cancel any existing active timeouts first if force is used
                EscrowTimeout.cancel_active_timeouts_for_transaction(txn.id)

                # Calculate countdown in seconds from now
                countdown_seconds = int((expires_at - timezone.now()).total_seconds())

                # Schedule the task
                task_result = timeout_config["task"].apply_async(
                    args=[txn.id],
                    countdown=countdown_seconds,
                )

                # Create timeout record
                EscrowTimeout.objects.create(
                    transaction=txn,
                    timeout_type=timeout_config["timeout_type"],
                    from_status=txn.status,
                    to_status=timeout_config["to_status"],
                    expires_at=expires_at,
                    celery_task_id=task_result.id,
                )

        return True

    def _calculate_expiration_time(self, txn, timeout_config):
        """Calculate when the timeout should expire for this transaction"""

        # Get the relevant timestamp for this transaction status
        base_time = None

        if txn.status == "delivered":
            # Use when it was marked as delivered
            base_time = self._get_status_timestamp(txn, "delivered")
            if not base_time:
                # Fallback to updated_at if no specific timestamp found
                base_time = txn.updated_at

        elif txn.status == "inspection":
            # Use when inspection period started
            base_time = self._get_status_timestamp(txn, "inspection")
            if not base_time:
                # Could also check if there's an inspection_start_date field
                if hasattr(txn, "inspection_start_date") and txn.inspection_start_date:
                    base_time = txn.inspection_start_date
                else:
                    base_time = txn.updated_at

        elif txn.status == "disputed":
            # Use when it was marked as disputed
            base_time = self._get_status_timestamp(txn, "disputed")
            if not base_time:
                base_time = txn.updated_at

        elif txn.status == "payment_received":
            # Use when payment was received
            base_time = self._get_status_timestamp(txn, "payment_received")
            if not base_time:
                base_time = txn.updated_at

        if not base_time:
            return None

        # Calculate expiration time
        expires_at = base_time + timedelta(days=timeout_config["days"])

        return expires_at

    def _get_status_timestamp(self, txn, status):
        """Get the timestamp when a transaction entered a specific status"""
        try:
            # Look for the most recent history entry for this status
            history_entry = (
                TransactionHistory.objects.filter(transaction=txn, status=status)
                .order_by("-created_at")
                .first()
            )

            if history_entry:
                return history_entry.created_at

            # If no history found, check if the current status matches
            if txn.status == status:
                return txn.updated_at

        except Exception as e:
            self.stdout.write(
                self.style.WARNING(
                    f"  Error getting status timestamp for transaction {txn.id}: {str(e)}"
                )
            )

        return None

    def _validate_migration_safety(self):
        """Perform safety checks before migration"""
        # Check if Celery is running
        from celery import current_app

        try:
            # Try to inspect active queues
            inspect = current_app.control.inspect()
            stats = inspect.stats()
            if not stats:
                self.stdout.write(
                    self.style.WARNING(
                        "Warning: Could not connect to Celery workers. Tasks may not be processed."
                    )
                )
        except Exception:
            self.stdout.write(
                self.style.WARNING(
                    "Warning: Could not verify Celery status. Ensure Celery workers are running."
                )
            )

    def _validate_current_state(self):
        """Validate the current state of transactions and timeouts"""
        self.stdout.write("Validating current state...\n")

        # Check for orphaned timeouts
        orphaned_timeouts = EscrowTimeout.objects.filter(
            transaction__isnull=True
        ).count()

        if orphaned_timeouts > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"Found {orphaned_timeouts} orphaned timeout records"
                )
            )

        # Check for transactions with multiple active timeouts
        from django.db.models import Count

        transactions_with_multiple_timeouts = EscrowTransaction.objects.annotate(
            active_timeout_count=Count(
                "escrowtimeout",
                filter=models.Q(
                    escrowtimeout__is_executed=False, escrowtimeout__is_cancelled=False
                ),
            )
        ).filter(active_timeout_count__gt=1)

        if transactions_with_multiple_timeouts.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"Found {transactions_with_multiple_timeouts.count()} transactions with multiple active timeouts"
                )
            )

        # Check for expired but not executed timeouts
        expired_timeouts = EscrowTimeout.objects.filter(
            expires_at__lt=timezone.now(), is_executed=False, is_cancelled=False
        ).count()

        if expired_timeouts > 0:
            self.stdout.write(
                self.style.ERROR(
                    f"Found {expired_timeouts} expired but not executed timeouts"
                )
            )

        self.stdout.write(self.style.SUCCESS("Validation completed"))
