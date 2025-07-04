#!/bin/bash

# Worker startup script for production
set -e

# Configuration
PROJECT_NAME="safetrade"
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
