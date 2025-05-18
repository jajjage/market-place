from subprocess import check_call


def run_worker():
    try:
        # Use the Python module approach which is more reliable
        check_call(
            ["python", "-m", "celery", "-A", "conf", "worker", "--loglevel=info"]
        )
    except FileNotFoundError:
        print(
            "Error: Celery not found. Make sure it's installed with 'pip install celery'"
        )


def run_beat():
    try:
        check_call(["python", "-m", "celery", "-A", "conf", "beat", "--loglevel=info"])
    except FileNotFoundError:
        print(
            "Error: Celery not found. Make sure it's installed with 'pip install celery'"
        )
