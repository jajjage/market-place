# apps/transactions/tasks/periodic_migration.py
import logging
from celery import shared_task
from django.core.management import call_command
from django.db import models
from django.utils import timezone
from datetime import timedelta

from apps.core.tasks import BaseTaskWithRetry
from apps.transactions.models import EscrowTransaction, EscrowTimeout
from apps.transactions.config.escrow_transition import EscrowTransitionConfig

logger = logging.getLogger("periodic_migration")


@shared_task(bind=True, base=BaseTaskWithRetry)
def ensure_timeout_scheduling(self, max_age_hours=2):
    """
    Periodic task to ensure all eligible transactions have timeout scheduling.
    This runs every few minutes to catch any transactions that may have missed
    their timeout scheduling due to race conditions or service interruptions.
    """

    try:
        logger.info(
            f"Running periodic timeout scheduling check (max_age_hours={max_age_hours})"
        )

        # Use the management command to do the actual work
        call_command(
            "migrate_to_timeout_system",
            "--quiet",
            f"--max-age-hours={max_age_hours}",
            "--batch-size=50",  # Smaller batches for frequent runs
        )

        logger.info("Periodic timeout scheduling check completed successfully")
        return "Periodic timeout scheduling completed"

    except Exception as e:
        logger.error(f"Error in periodic timeout scheduling: {str(e)}")
        raise


@shared_task(bind=True, base=BaseTaskWithRetry)
def validate_timeout_consistency(self):
    """
    Periodic task to validate timeout consistency and report any issues.
    This helps identify problems with the timeout system.
    """
    try:
        logger.info("Running timeout consistency validation")

        issues = []

        # Check for transactions in timeout-eligible statuses without active timeouts
        timeout_statuses = list(EscrowTransitionConfig.TIMEOUT_CONFIGS.keys())

        transactions_without_timeouts = (
            EscrowTransaction.objects.filter(status__in=timeout_statuses)
            .exclude(
                escrowtimeout__is_executed=False, escrowtimeout__is_cancelled=False
            )
            .count()
        )

        if transactions_without_timeouts > 0:
            issues.append(
                f"{transactions_without_timeouts} transactions missing timeout scheduling"
            )

        # Check for expired timeouts that weren't executed
        expired_timeouts = EscrowTimeout.objects.filter(
            expires_at__lt=timezone.now()
            - timedelta(minutes=5),  # 5 minute grace period
            is_executed=False,
            is_cancelled=False,
        ).count()

        if expired_timeouts > 0:
            issues.append(f"{expired_timeouts} expired timeouts not executed")

        # Check for transactions with multiple active timeouts
        from django.db.models import Count

        transactions_with_multiple_timeouts = (
            EscrowTransaction.objects.annotate(
                active_timeout_count=Count(
                    "escrowtimeout",
                    filter=models.Q(
                        escrowtimeout__is_executed=False,
                        escrowtimeout__is_cancelled=False,
                    ),
                )
            )
            .filter(active_timeout_count__gt=1)
            .count()
        )

        if transactions_with_multiple_timeouts > 0:
            issues.append(
                f"{transactions_with_multiple_timeouts} transactions with multiple active timeouts"
            )

        if issues:
            logger.warning(f"Timeout consistency issues found: {'; '.join(issues)}")
            # You might want to send alerts here
            return {"status": "issues_found", "issues": issues}
        else:
            logger.info("Timeout consistency validation passed")
            return {"status": "ok", "issues": []}

    except Exception as e:
        logger.error(f"Error in timeout consistency validation: {str(e)}")
        raise


@shared_task(bind=True, base=BaseTaskWithRetry)
def auto_fix_timeout_issues(self):
    """
    Periodic task to automatically fix common timeout issues.
    This should run less frequently than the validation task.
    """
    try:
        logger.info("Running automatic timeout issue fixes")

        fixes_applied = []

        # Fix 1: Cancel duplicate active timeouts (keep the most recent one)
        from django.db.models import Count

        transactions_with_multiple_timeouts = EscrowTransaction.objects.annotate(
            active_timeout_count=Count(
                "escrowtimeout",
                filter=models.Q(
                    escrowtimeout__is_executed=False, escrowtimeout__is_cancelled=False
                ),
            )
        ).filter(active_timeout_count__gt=1)

        duplicate_fixes = 0
        for txn in transactions_with_multiple_timeouts:
            active_timeouts = EscrowTimeout.objects.filter(
                transaction=txn, is_executed=False, is_cancelled=False
            ).order_by("-created_at")

            # Keep the most recent, cancel the rest
            for timeout in active_timeouts[1:]:
                timeout.cancel("Duplicate timeout cancelled automatically")
                duplicate_fixes += 1

        if duplicate_fixes > 0:
            fixes_applied.append(f"Cancelled {duplicate_fixes} duplicate timeouts")

        # Fix 2: Handle expired timeouts that should have been executed
        expired_timeouts = EscrowTimeout.objects.filter(
            expires_at__lt=timezone.now()
            - timedelta(minutes=10),  # 10 minute grace period
            is_executed=False,
            is_cancelled=False,
        )

        expired_fixes = 0
        for timeout in expired_timeouts:
            try:
                # Try to execute the appropriate transition task
                task_map = {
                    "inspection_start": "schedule_auto_inspection",
                    "inspection_end": "schedule_auto_completion",
                    "dispute_refund": "auto_refund_disputed_transaction",
                    "shipping": "schedule_shipping_timeout",
                }

                task_name = task_map.get(timeout.timeout_type)
                if task_name:
                    # Import and execute the task
                    from apps.transactions.tasks.transitions_tasks import (
                        schedule_auto_inspection,
                        schedule_auto_completion,
                        auto_refund_disputed_transaction,
                        schedule_shipping_timeout,
                    )

                    task_func_map = {
                        "schedule_auto_inspection": schedule_auto_inspection,
                        "schedule_auto_completion": schedule_auto_completion,
                        "auto_refund_disputed_transaction": auto_refund_disputed_transaction,
                        "schedule_shipping_timeout": schedule_shipping_timeout,
                    }

                    task_func = task_func_map.get(task_name)
                    if task_func:
                        task_func.apply_async(args=[timeout.transaction_id])
                        expired_fixes += 1
                else:
                    # Unknown timeout type, cancel it
                    timeout.cancel("Unknown timeout type - cancelled automatically")
                    expired_fixes += 1

            except Exception as e:
                logger.error(f"Failed to fix expired timeout {timeout.id}: {str(e)}")
                timeout.cancel(f"Auto-fix failed: {str(e)}")

        if expired_fixes > 0:
            fixes_applied.append(f"Fixed {expired_fixes} expired timeouts")

        if fixes_applied:
            logger.info(f"Automatic fixes applied: {'; '.join(fixes_applied)}")
            return {"status": "fixes_applied", "fixes": fixes_applied}
        else:
            logger.info("No automatic fixes needed")
            return {"status": "no_fixes_needed", "fixes": []}

    except Exception as e:
        logger.error(f"Error in automatic timeout issue fixes: {str(e)}")
        raise


@shared_task(bind=True, base=BaseTaskWithRetry)
def generate_timeout_health_report(self):
    """
    Generate a health report for the timeout system.
    This provides insights into timeout system performance.
    """
    try:
        logger.info("Generating timeout system health report")

        now = timezone.now()

        # Basic statistics
        total_active_timeouts = EscrowTimeout.objects.filter(
            is_executed=False, is_cancelled=False
        ).count()

        total_executed_timeouts = EscrowTimeout.objects.filter(
            is_executed=True, updated_at__gte=now - timedelta(days=7)  # Last 7 days
        ).count()

        total_cancelled_timeouts = EscrowTimeout.objects.filter(
            is_cancelled=True, updated_at__gte=now - timedelta(days=7)  # Last 7 days
        ).count()

        # Timeout type breakdown
        timeout_breakdown = {}
        for timeout_type in [
            "inspection_start",
            "inspection_end",
            "dispute_refund",
            "shipping",
        ]:
            active_count = EscrowTimeout.objects.filter(
                timeout_type=timeout_type, is_executed=False, is_cancelled=False
            ).count()

            executed_count = EscrowTimeout.objects.filter(
                timeout_type=timeout_type,
                is_executed=True,
                updated_at__gte=now - timedelta(days=7),
            ).count()

            timeout_breakdown[timeout_type] = {
                "active": active_count,
                "executed_last_7_days": executed_count,
            }

        # Upcoming timeouts (next 24 hours)
        upcoming_timeouts = EscrowTimeout.objects.filter(
            expires_at__gte=now,
            expires_at__lte=now + timedelta(hours=24),
            is_executed=False,
            is_cancelled=False,
        ).count()

        # Overdue timeouts
        overdue_timeouts = EscrowTimeout.objects.filter(
            expires_at__lt=now, is_executed=False, is_cancelled=False
        ).count()

        report = {
            "timestamp": now.isoformat(),
            "active_timeouts": total_active_timeouts,
            "executed_last_7_days": total_executed_timeouts,
            "cancelled_last_7_days": total_cancelled_timeouts,
            "upcoming_24h": upcoming_timeouts,
            "overdue": overdue_timeouts,
            "timeout_breakdown": timeout_breakdown,
            "health_status": "healthy" if overdue_timeouts == 0 else "issues_detected",
        }

        logger.info(f"Timeout health report generated: {report}")

        # You might want to store this report in a model or send it to monitoring
        return report

    except Exception as e:
        logger.error(f"Error generating timeout health report: {str(e)}")
        raise
