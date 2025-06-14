# ============================================
# WORKER CALCULATION AND CONFIGURATION
# ============================================

"""
WORKER CALCULATION FORMULA:

For 100 tasks, consider:
1. Task duration (how long each task takes)
2. Task frequency (how often tasks are created)
3. Server resources (CPU cores, RAM)
4. Task types (CPU-bound vs I/O-bound)

RECOMMENDED SETUP FOR 100 TASKS:
- Light tasks (< 30 seconds): 2-4 workers
- Medium tasks (30 seconds - 5 minutes): 4-8 workers  
- Heavy tasks (> 5 minutes): 8-16 workers
- Mixed workload: 6-12 workers

GENERAL RULE:
- CPU-bound tasks: 1 worker per CPU core
- I/O-bound tasks: 2-4 workers per CPU core
- Mixed workload: 1.5-2 workers per CPU core
"""

# ============================================
# SETTINGS CONFIGURATION
# ============================================

# settings/celery_workers.py
import os
import multiprocessing

# Get system information
CPU_CORES = multiprocessing.cpu_count()
AVAILABLE_MEMORY_GB = 8  # Adjust based on your server

# Worker configuration based on environment
CELERY_WORKER_CONFIGS = {
    'development': {
        'workers': min(4, CPU_CORES),
        'concurrency': 2,
        'prefetch_multiplier': 1,
        'max_tasks_per_child': 1000,
        'max_memory_per_child': 200000,  # 200MB in KB
    },
    'production': {
        'workers': min(8, CPU_CORES * 2),
        'concurrency': 4,
        'prefetch_multiplier': 4,
        'max_tasks_per_child': 5000,
        'max_memory_per_child': 500000,  # 500MB in KB
    },
    'high_load': {
        'workers': min(16, CPU_CORES * 3),
        'concurrency': 6,
        'prefetch_multiplier': 2,
        'max_tasks_per_child': 2000,
        'max_memory_per_child': 300000,  # 300MB in KB
    }
}

def get_worker_config():
    """Get worker configuration based on environment"""
    env = os.environ.get('CELERY_WORKER_ENV', 'development').lower()
    return CELERY_WORKER_CONFIGS.get(env, CELERY_WORKER_CONFIGS['development'])

# ============================================
# DJANGO SETTINGS INTEGRATION
# ============================================

# settings/base.py
from .celery_workers import get_worker_config

# Get worker configuration
WORKER_CONFIG = get_worker_config()

# Celery worker settings
CELERY_WORKER_PREFETCH_MULTIPLIER = WORKER_CONFIG['prefetch_multiplier']
CELERY_WORKER_MAX_TASKS_PER_CHILD = WORKER_CONFIG['max_tasks_per_child']
CELERY_WORKER_MAX_MEMORY_PER_CHILD = WORKER_CONFIG['max_memory_per_child']
CELERY_WORKER_CONCURRENCY = WORKER_CONFIG['concurrency']

# Task routing for different queues
CELERY_TASK_ROUTES = {
    # High priority tasks
    'apps.transactions.tasks.transitions_tasks.check_expired_transactions': {
        'queue': 'high_priority',
        'routing_key': 'high_priority',
    },
    'apps.transactions.tasks.periodic_migration.ensure_timeout_scheduling': {
        'queue': 'high_priority',
        'routing_key': 'high_priority',
    },
    
    # Medium priority tasks
    'apps.transactions.tasks.periodic_migration.validate_timeout_consistency': {
        'queue': 'medium_priority',
        'routing_key': 'medium_priority',
    },
    'apps.transactions.tasks.periodic_migration.auto_fix_timeout_issues': {
        'queue': 'medium_priority',
        'routing_key': 'medium_priority',
    },
    
    # Low priority tasks
    'apps.transactions.tasks.periodic_migration.generate_timeout_health_report': {
        'queue': 'low_priority',
        'routing_key': 'low_priority',
    },
    'apps.transactions.tasks.transitions_tasks.cleanup_completed_timeouts': {
        'queue': 'low_priority',
        'routing_key': 'low_priority',
    },
    
    # Default queue for other tasks
    'apps.transactions.tasks.*': {
        'queue': 'default',
        'routing_key': 'default',
    },
}

# Queue configuration
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_QUEUES = {
    'high_priority': {
        'exchange': 'high_priority',
        'exchange_type': 'direct',
        'routing_key': 'high_priority',
    },
    'medium_priority': {
        'exchange': 'medium_priority',
        'exchange_type': 'direct',
        'routing_key': 'medium_priority',
    },
    'low_priority': {
        'exchange': 'low_priority',
        'exchange_type': 'direct',
        'routing_key': 'low_priority',
    },
    'default': {
        'exchange': 'default',
        'exchange_type': 'direct',
        'routing_key': 'default',
    },
}

# ============================================
# WORKER STARTUP SCRIPTS
# ============================================

# scripts/start_workers.sh
#!/bin/bash

# Worker startup script for production
set -e

# Configuration
PROJECT_NAME="myproject"
DJANGO_ENV=${DJANGO_ENV:-production}
CELERY_WORKER_ENV=${CELERY_WORKER_ENV:-production}
LOG_DIR="/var/log/celery"
PID_DIR="/var/run/celery"

# Create directories
mkdir -p $LOG_DIR $PID_DIR

# Export environment variables
export DJANGO_ENV=$DJANGO_ENV
export CELERY_WORKER_ENV=$CELERY_WORKER_ENV

# Function to start a worker
start_worker() {
    local queue=$1
    local concurrency=$2
    local worker_name="${PROJECT_NAME}_${queue}_worker"
    
    echo "Starting worker for queue: $queue with concurrency: $concurrency"
    
    celery -A $PROJECT_NAME worker \
        --loglevel=info \
        --queues=$queue \
        --concurrency=$concurrency \
        --hostname=${worker_name}@%h \
        --pidfile=$PID_DIR/${worker_name}.pid \
        --logfile=$LOG_DIR/${worker_name}.log \
        --detach
}

# Start workers for different queues
case $CELERY_WORKER_ENV in
    "development")
        start_worker "high_priority,medium_priority,default,low_priority" 2
        ;;
    "production")
        start_worker "high_priority" 2
        start_worker "medium_priority" 3
        start_worker "default" 4
        start_worker "low_priority" 2
        ;;
    "high_load")
        start_worker "high_priority" 4
        start_worker "medium_priority" 6
        start_worker "default" 8
        start_worker "low_priority" 4
        ;;
esac

echo "All workers started successfully!"

# ============================================
# DOCKER CONFIGURATION
# ============================================

# docker-compose.yml
version: '3.8'

services:
  # Redis for broker and result backend
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  # Main web application
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DJANGO_ENV=production
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    depends_on:
      - redis

  # High priority worker
  celery-worker-high:
    build: .
    command: celery -A myproject worker --loglevel=info --queues=high_priority --concurrency=2 --hostname=high_priority_worker@%h
    environment:
      - DJANGO_ENV=production
      - CELERY_WORKER_ENV=production
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    depends_on:
      - redis
    volumes:
      - ./logs:/var/log/celery
    restart: unless-stopped

  # Medium priority worker
  celery-worker-medium:
    build: .
    command: celery -A myproject worker --loglevel=info --queues=medium_priority --concurrency=3 --hostname=medium_priority_worker@%h
    environment:
      - DJANGO_ENV=production
      - CELERY_WORKER_ENV=production
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    depends_on:
      - redis
    volumes:
      - ./logs:/var/log/celery
    restart: unless-stopped

  # Default queue worker
  celery-worker-default:
    build: .
    command: celery -A myproject worker --loglevel=info --queues=default --concurrency=4 --hostname=default_worker@%h
    environment:
      - DJANGO_ENV=production
      - CELERY_WORKER_ENV=production
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    depends_on:
      - redis
    volumes:
      - ./logs:/var/log/celery
    restart: unless-stopped

  # Low priority worker
  celery-worker-low:
    build: .
    command: celery -A myproject worker --loglevel=info --queues=low_priority --concurrency=2 --hostname=low_priority_worker@%h
    environment:
      - DJANGO_ENV=production
      - CELERY_WORKER_ENV=production
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    depends_on:
      - redis
    volumes:
      - ./logs:/var/log/celery
    restart: unless-stopped

  # Celery Beat scheduler
  celery-beat:
    build: .
    command: celery -A myproject beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    environment:
      - DJANGO_ENV=production
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    depends_on:
      - redis
      - web
    volumes:
      - ./logs:/var/log/celery
    restart: unless-stopped

  # Celery Flower for monitoring
  celery-flower:
    build: .
    command: celery -A myproject flower --port=5555
    ports:
      - "5555:5555"
    environment:
      - DJANGO_ENV=production
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    depends_on:
      - redis
    restart: unless-stopped

volumes:
  redis_data:

# ============================================
# SYSTEMD SERVICE FILES (for Linux servers)
# ============================================

# /etc/systemd/system/celery-worker@.service
[Unit]
Description=Celery Worker %i
After=network.target

[Service]
Type=forking
User=celery
Group=celery
EnvironmentFile=/etc/default/celery
ExecStart=/opt/myproject/venv/bin/celery -A myproject worker --detach --loglevel=info --queues=%i --concurrency=4 --hostname=%i_worker@%%h --pidfile=/var/run/celery/%i.pid --logfile=/var/log/celery/%i.log
ExecStop=/bin/kill -TERM $MAINPID
ExecReload=/bin/kill -HUP $MAINPID
KillMode=mixed
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

# /etc/default/celery
DJANGO_ENV=production
CELERY_WORKER_ENV=production
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Enable and start services:
# sudo systemctl enable celery-worker@high_priority
# sudo systemctl enable celery-worker@medium_priority
# sudo systemctl enable celery-worker@default
# sudo systemctl enable celery-worker@low_priority
# sudo systemctl start celery-worker@high_priority
# sudo systemctl start celery-worker@medium_priority
# sudo systemctl start celery-worker@default
# sudo systemctl start celery-worker@low_priority

# ============================================
# MONITORING AND SCALING COMMANDS
# ============================================

# Monitor worker status
# celery -A myproject inspect active
# celery -A myproject inspect stats
# celery -A myproject inspect registered

# Scale workers dynamically
# celery -A myproject control pool_grow 2  # Add 2 worker processes
# celery -A myproject control pool_shrink 1  # Remove 1 worker process

# Monitor queue lengths
# celery -A myproject inspect active_queues

# Purge queues (if needed)
# celery -A myproject purge -Q high_priority
# celery -A myproject purge -Q medium_priority
# celery -A myproject purge -Q default
# celery -A myproject purge -Q low_priority

# ============================================
# PERFORMANCE TUNING NOTES
# ============================================

"""
WORKER PERFORMANCE TIPS:

1. CONCURRENCY:
   - Start with 1-2 workers per CPU core
   - Monitor CPU and memory usage
   - Adjust based on task characteristics

2. PREFETCH MULTIPLIER:
   - Higher values = better throughput
   - Lower values = better load balancing
   - Set 1 for long-running tasks, 4+ for short tasks

3. MAX TASKS PER CHILD:
   - Prevents memory leaks
   - Restart workers after N tasks
   - Balance between performance and memory

4. QUEUE SEPARATION:
   - Critical tasks → high priority queue
   - Background tasks → low priority queue
   - Different workers per queue

5. MONITORING:
   - Use Flower for real-time monitoring
   - Monitor queue lengths
   - Track task success/failure rates
   - Monitor worker memory usage

RECOMMENDED SETUP FOR 100+ TASKS:
- 4 CPU cores: 6-8 workers total
- 8 CPU cores: 10-16 workers total
- 16 CPU cores: 20-32 workers total
"""