# Celery Background Workers & Tasks Routing

This guide details our Celery configuration, worker calculations, queue rules, and startup commands.

---

## 1. Concurrency & Queue Configuration

### Queue Priorities
To ensure that time-critical actions (like escrow timeouts) are never blocked by heavy reporting tasks, we segment background jobs into four queues:

1.  **high_priority**: For critical escrow checks, transaction status transitions, and immediate event webhooks.
2.  **medium_priority**: For data reconciliation and auto-fixing timeout database records.
3.  **low_priority**: For log cleanup tasks and analytics reports generation.
4.  **default**: For all standard asynchronous tasks (e.g. notifications sending).

### Settings & Routing Setup
```python
CELERY_TASK_ROUTES = {
    # High Priority
    'apps.transactions.tasks.transitions_tasks.check_expired_transactions': {
        'queue': 'high_priority',
    },
    # Low Priority
    'apps.transactions.tasks.transitions_tasks.cleanup_completed_timeouts': {
        'queue': 'low_priority',
    },
}
```

---

## 2. Docker & Worker Execution

### Local Docker Compose Commands
In development and production, we launch separate worker instances target-configured to listen only to specific queues to avoid starvation:

- **Default Worker**:
  ```bash
  celery -A safetrade worker --loglevel=info --queues=high_priority,medium_priority,low_priority,default --concurrency=4
  ```
- **Flower Monitoring Dashboard**:
  Accessible at http://localhost:5555
  ```bash
  celery -A safetrade flower --port=5555
  ```
