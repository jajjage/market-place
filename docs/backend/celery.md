# Celery Background Workers & Tasks Routing

This guide details the celery configuration, environment-specific task scheduler, queue routing tables, and startup scripts.

---

## 1. Concurrency & Queue Configuration

To ensure time-critical tasks (like payment timeouts) are never blocked by heavy batch jobs, the platform routes tasks to four distinct queues:

1.  **`high_priority`**: For immediate transition expiration checks and payment hook events.
2.  **`medium_priority`**: For timeout consistency validations and automatic data corrections.
3.  **`low_priority`**: For weekly health reports generation and database cleaning.
4.  **`default`**: For standard asynchronous tasks (e.g., messaging and mail notifications).

### Routing Configuration
Task queues are configured in the Django settings:
```python
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_QUEUES = {
    'high_priority': {'exchange': 'high_priority', 'exchange_type': 'direct', 'routing_key': 'high_priority'},
    'medium_priority': {'exchange': 'medium_priority', 'exchange_type': 'direct', 'routing_key': 'medium_priority'},
    'low_priority': {'exchange': 'low_priority', 'exchange_type': 'direct', 'routing_key': 'low_priority'},
    'default': {'exchange': 'default', 'exchange_type': 'direct', 'routing_key': 'default'},
}
```

---

## 2. Environment-Specific Beat Schedule

The Celery Beat scheduler loads schedule templates depending on the `DJANGO_ENV` environment variable, defined in [celery_beat_schedule.py](file:///c:/Users/musta/fasu-marketplace/market-place/safetrade/settings/celery/celery_beat_schedule.py):

### Production Schedule (`CELERY_BEAT_SCHEDULE`)
- **`ensure-timeout-scheduling`**: Runs every 5 minutes (processes transactions updated in the last 2 hours).
- **`validate-timeout-consistency`**: Runs every 15 minutes.
- **`auto-fix-timeout-issues`**: Runs every hour at minute 30.
- **`check-expired-transactions`**: Runs every 30 minutes.
- **`update-product-popularity-scores`**: Runs every hour.
- **`cleanup-completed-timeouts`**: Runs daily at 2:00 AM (removes records older than 30 days).
- **`cleanup-old-search-logs`**: Runs daily at 3:30 AM.

### Development Schedule (`CELERY_BEAT_SCHEDULE_DEV`)
Runs validation, auto-fixing, expiration checks, and popularity calculations at highly accelerated intervals (every 2 to 10 minutes) for rapid debugging.

### Testing Schedule (`CELERY_BEAT_SCHEDULE_TEST`)
Configured to run tasks every 1 to 2 minutes, enabling quick unit and integration test assertions without sleep stalls.

---

## 3. Deployment & Start Commands

### Local Compose Services
Our [docker-compose.yml](file:///c:/Users/musta/fasu-marketplace/market-place/docker-compose.yml) starts three workers plus beat and monitoring tools:
- **`celery_worker_default`**: Handles the default, medium, and high priority queues.
  ```bash
  poetry run celery -A safetrade worker --loglevel=info --queues=high_priority,medium_priority,low_priority,default --concurrency=4
  ```
- **`celery_beat`**: Starts the beat scheduler.
  ```bash
  poetry run celery -A safetrade beat --loglevel=info
  ```
- **`celery_flower`**: Starts the monitoring tool on port `5555`.
  ```bash
  poetry run celery -A safetrade flower --port=5555
  ```
