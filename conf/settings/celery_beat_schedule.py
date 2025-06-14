from celery.schedules import crontab

# Celery Beat Schedule Configuration for Timeout System
CELERY_BEAT_SCHEDULE = {
    # ============================================
    # TIMEOUT MIGRATION AND SCHEDULING
    # ============================================
    # Ensure timeout scheduling every 5 minutes
    # This catches any transactions that might have missed timeout scheduling
    "ensure-timeout-scheduling": {
        "task": "apps.transactions.tasks.periodic_migration.ensure_timeout_scheduling",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
        "kwargs": {
            "max_age_hours": 2
        },  # Only process transactions updated in last 2 hours
        "options": {
            "expires": 300,  # Task expires after 5 minutes
            "retry": True,
            "retry_policy": {
                "max_retries": 3,
                "interval_start": 10,
                "interval_step": 10,
                "interval_max": 60,
            },
        },
    },
    # ============================================
    # TIMEOUT SYSTEM VALIDATION
    # ============================================
    # Validate timeout consistency every 15 minutes
    "validate-timeout-consistency": {
        "task": "apps.transactions.tasks.periodic_migration.validate_timeout_consistency",
        "schedule": crontab(minute="*/15"),  # Every 15 minutes
        "options": {
            "expires": 600,  # Task expires after 10 minutes
        },
    },
    # Auto-fix timeout issues every hour
    "auto-fix-timeout-issues": {
        "task": "apps.transactions.tasks.periodic_migration.auto_fix_timeout_issues",
        "schedule": crontab(minute=30),  # Every hour at minute 30
        "options": {
            "expires": 1800,  # Task expires after 30 minutes
            "retry": True,
            "retry_policy": {
                "max_retries": 2,
                "interval_start": 60,
                "interval_step": 60,
                "interval_max": 300,
            },
        },
    },
    # ============================================
    # MONITORING AND REPORTING
    # ============================================
    # Generate health report every 4 hours
    "generate-timeout-health-report": {
        "task": "apps.transactions.tasks.periodic_migration.generate_timeout_health_report",
        "schedule": crontab(minute=0, hour="*/4"),  # Every 4 hours
        "options": {
            "expires": 3600,  # Task expires after 1 hour
        },
    },
    # ============================================
    # EXISTING TIMEOUT TASKS
    # ============================================
    # Check for expired transactions (safety net) every 30 minutes
    "check-expired-transactions": {
        "task": "apps.transactions.tasks.transitions_tasks.check_expired_transactions",
        "schedule": crontab(minute="*/30"),  # Every 30 minutes
        "options": {
            "expires": 1200,  # Task expires after 20 minutes
            "retry": True,
            "retry_policy": {
                "max_retries": 3,
                "interval_start": 30,
                "interval_step": 30,
                "interval_max": 180,
            },
        },
    },
    # Cleanup old timeout records daily at 2 AM
    "cleanup-completed-timeouts": {
        "task": "apps.transactions.tasks.transitions_tasks.cleanup_completed_timeouts",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2:00 AM
        "kwargs": {"days_old": 30},  # Clean up records older than 30 days
        "options": {
            "expires": 3600,  # Task expires after 1 hour
        },
    },
    # ============================================
    # COMPREHENSIVE MIGRATION (FALLBACK)
    # ============================================
    # Run comprehensive migration daily at 1 AM (catches any edge cases)
    "comprehensive-timeout-migration": {
        "task": "apps.transactions.tasks.periodic_migration.comprehensive_migration",
        "schedule": crontab(hour=1, minute=0),  # Daily at 1:00 AM
        "options": {
            "expires": 7200,  # Task expires after 2 hours
            "retry": True,
            "retry_policy": {
                "max_retries": 2,
                "interval_start": 300,
                "interval_step": 300,
                "interval_max": 900,
            },
        },
    },
}

# Additional configuration for development/testing environments
CELERY_BEAT_SCHEDULE_DEV = {
    # More frequent scheduling for development
    "ensure-timeout-scheduling-dev": {
        "task": "apps.transactions.tasks.periodic_migration.ensure_timeout_scheduling",
        "schedule": crontab(minute="*/2"),  # Every 2 minutes in dev
        "kwargs": {"max_age_hours": 1},  # Process transactions updated in last 1 hour
        "options": {
            "expires": 120,  # Task expires after 2 minutes
            "retry": True,
            "retry_policy": {
                "max_retries": 2,
                "interval_start": 5,
                "interval_step": 5,
                "interval_max": 30,
            },
        },
    },
    # More frequent validation for development
    "validate-timeout-consistency-dev": {
        "task": "apps.transactions.tasks.periodic_migration.validate_timeout_consistency",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes in dev
        "options": {
            "expires": 300,  # Task expires after 5 minutes
        },
    },
    # Quick auto-fix for development
    "auto-fix-timeout-issues-dev": {
        "task": "apps.transactions.tasks.periodic_migration.auto_fix_timeout_issues",
        "schedule": crontab(minute="*/10"),  # Every 10 minutes in dev
        "options": {
            "expires": 600,  # Task expires after 10 minutes
            "retry": True,
            "retry_policy": {
                "max_retries": 1,
                "interval_start": 30,
                "interval_step": 30,
                "interval_max": 60,
            },
        },
    },
    # Frequent health reports for development
    "generate-timeout-health-report-dev": {
        "task": "apps.transactions.tasks.periodic_migration.generate_timeout_health_report",
        "schedule": crontab(minute="*/30"),  # Every 30 minutes in dev
        "options": {
            "expires": 900,  # Task expires after 15 minutes
        },
    },
    # More frequent expired transaction checks for development
    "check-expired-transactions-dev": {
        "task": "apps.transactions.tasks.transitions_tasks.check_expired_transactions",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes in dev
        "options": {
            "expires": 300,  # Task expires after 5 minutes
            "retry": True,
            "retry_policy": {
                "max_retries": 2,
                "interval_start": 10,
                "interval_step": 10,
                "interval_max": 60,
            },
        },
    },
    # Development cleanup (more frequent, less data)
    "cleanup-completed-timeouts-dev": {
        "task": "apps.transactions.tasks.transitions_tasks.cleanup_completed_timeouts",
        "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours in dev
        "kwargs": {"days_old": 7},  # Clean up records older than 7 days in dev
        "options": {
            "expires": 1800,  # Task expires after 30 minutes
        },
    },
    # Comprehensive migration for development (more frequent)
    "comprehensive-timeout-migration-dev": {
        "task": "apps.transactions.tasks.periodic_migration.comprehensive_migration",
        "schedule": crontab(minute=0, hour="*/4"),  # Every 4 hours in dev
        "options": {
            "expires": 3600,  # Task expires after 1 hour
            "retry": True,
            "retry_policy": {
                "max_retries": 1,
                "interval_start": 120,
                "interval_step": 120,
                "interval_max": 300,
            },
        },
    },
}

# Testing configuration (even more frequent for testing)
CELERY_BEAT_SCHEDULE_TEST = {
    # Very frequent scheduling for testing
    "ensure-timeout-scheduling-test": {
        "task": "apps.transactions.tasks.periodic_migration.ensure_timeout_scheduling",
        "schedule": crontab(minute="*/1"),  # Every 1 minute in test
        "kwargs": {
            "max_age_hours": 0.5
        },  # Process transactions updated in last 30 minutes
        "options": {
            "expires": 60,  # Task expires after 1 minute
            "retry": False,  # No retries in test
        },
    },
    "validate-timeout-consistency-test": {
        "task": "apps.transactions.tasks.periodic_migration.validate_timeout_consistency",
        "schedule": crontab(minute="*/2"),  # Every 2 minutes in test
        "options": {
            "expires": 120,  # Task expires after 2 minutes
            "retry": False,
        },
    },
    "check-expired-transactions-test": {
        "task": "apps.transactions.tasks.transitions_tasks.check_expired_transactions",
        "schedule": crontab(minute="*/3"),  # Every 3 minutes in test
        "options": {
            "expires": 180,  # Task expires after 3 minutes
            "retry": False,
        },
    },
}


def get_celery_beat_schedule():
    """
    Get the appropriate Celery Beat schedule based on environment.

    Returns:
        dict: The appropriate schedule configuration
    """
    import os
    from django.conf import settings

    # Check environment variable first
    env = os.environ.get("DJANGO_ENV", "").lower()

    # Fallback to Django DEBUG setting
    if not env:
        env = "development" if getattr(settings, "DEBUG", False) else "production"

    if env == "test" or env == "testing":
        return CELERY_BEAT_SCHEDULE_TEST
    elif env == "development" or env == "dev":
        return CELERY_BEAT_SCHEDULE_DEV
    else:  # production, staging, etc.
        return CELERY_BEAT_SCHEDULE
