from subprocess import check_call


def run_worker_default():
    try:
        # Use the Python module approach which is more reliable
        check_call(
            [
                "python",
                "-m",
                "celery",
                "-A",
                "safetrade",
                "worker",
                "--loglevel=info",
                "--queues=high_priority,medium_priority,low_priority,default",
                "--concurrency=4",
                "--hostname=default_worker@%h",
            ]
        )
    except FileNotFoundError:
        print(
            "Error: Celery not found. Make sure it's installed with 'pip install celery'"
        )


def run_worker_low():
    try:
        # Use the Python module approach which is more reliable
        check_call(
            [
                "python",
                "-m",
                "celery",
                "-A",
                "safetrade",
                "worker",
                "--loglevel=info",
                "--queues=low_priority",
                "--concurrency=2",
                "--hostname=low_priority_worker@%h",
            ]
        )
    except FileNotFoundError:
        print(
            "Error: Celery not found. Make sure it's installed with 'pip install celery'"
        )


def run_worker_medium():
    try:
        # Use the Python module approach which is more reliable
        check_call(
            [
                "python",
                "-m",
                "celery",
                "-A",
                "safetrade",
                "worker",
                "--loglevel=info",
                "--queues=medium_priority",
                "--concurrency=3",
                "--hostname=medium_priority_worker@%h",
            ]
        )
    except FileNotFoundError:
        print(
            "Error: Celery not found. Make sure it's installed with 'pip install celery'"
        )


def run_worker_high():
    try:
        # Use the Python module approach which is more reliable
        check_call(
            [
                "python",
                "-m",
                "celery",
                "-A",
                "safetrade",
                "worker",
                "--loglevel=info",
                "--queues=high_priority",
                "--concurrency=5",
                "--hostname=high_priority_worker@%h",
            ]
        )
    except FileNotFoundError:
        print(
            "Error: Celery not found. Make sure it's installed with 'pip install celery'"
        )


def run_beat():
    try:
        check_call(["python", "-m", "celery", "-A", "safetrade", "beat", "--loglevel=info"])
    except FileNotFoundError:
        print(
            "Error: Celery not found. Make sure it's installed with 'pip install celery'"
        )


def run_flower():
    try:
        check_call(["python", "-m", "celery", "-A", "safetrade", "flower", "--port=5555"])
    except FileNotFoundError:
        print(
            "Error: Celery not found. Make sure it's installed with 'pip install celery'"
        )
