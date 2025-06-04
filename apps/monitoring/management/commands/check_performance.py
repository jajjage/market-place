# monitoring/management/commands/check_performance.py

from django.core.management.base import BaseCommand
from monitoring.utils import check_database_performance, check_cache_hit_ratio


class Command(BaseCommand):
    help = "Check DB slow queries and cache hit ratio, logging warnings if thresholds are exceeded."

    def handle(self, *args, **options):
        self.stdout.write("Running performance checks…")
        check_database_performance()
        ratio = check_cache_hit_ratio()
        self.stdout.write(f"Cache hit ratio is {ratio:.1f}%")
        self.stdout.write("Done.")
