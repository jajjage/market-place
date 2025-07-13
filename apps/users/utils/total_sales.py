from django.db.models import Sum, Q
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


def _month_bounds(dt):
    """Return (start_of_month, start_of_previous_month)."""
    start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev = (start - timedelta(days=1)).replace(day=1)
    return start, prev


def get_seller_sales_summary(user):
    now = timezone.now()
    current_month, previous_month = _month_bounds(now)

    active_statuses = [
        "payment_received",
        "shipped",
        "delivered",
        "completed",
        "inspection",
        "funds_released",
    ]

    # A single DB hit with multiple conditional sums
    agg = user.seller_transactions.aggregate(
        withdrawable_funds=Sum("total_amount", filter=Q(status="funds_released")),
        active_current=Sum(
            "total_amount",
            filter=Q(status__in=active_statuses, created_at__gte=current_month),
        ),
        active_previous=Sum(
            "total_amount",
            filter=Q(
                status__in=active_statuses,
                created_at__gte=previous_month,
                created_at__lt=current_month,
            ),
        ),
        active_all_time=Sum("total_amount", filter=Q(status__in=active_statuses)),
    )

    # Fallback zeros
    withdrawable = agg["withdrawable_funds"] or 0
    current = agg["active_current"] or 0
    previous = agg["active_previous"] or 0
    all_time = agg["active_all_time"] or 0

    # percentage change
    if previous > 0:
        pct = (current - previous) / previous * 100
    else:
        pct = 100 if current > 0 else 0

    return {
        "withdrawable_funds": withdrawable,
        "current_month_active_sales": current,
        "all_time_active_sales": all_time,
        "percentage_change": pct,
        "is_increase": pct >= 0,
    }


def get_detailed_seller_summary(user):
    now = timezone.now()
    current_month, previous_month = _month_bounds(now)

    active_statuses = ["payment_received", "shipped", "delivered"]

    # one DB hit for both active & withdrawable sums
    agg = user.seller_transactions.aggregate(
        withdraw_current=Sum(
            "total_amount",
            filter=Q(status="funds_released", created_at__gte=current_month),
        ),
        withdraw_prev=Sum(
            "total_amount",
            filter=Q(
                status="funds_released",
                created_at__gte=previous_month,
                created_at__lt=current_month,
            ),
        ),
        withdraw_all=Sum("total_amount", filter=Q(status="funds_released")),
        active_current=Sum(
            "total_amount",
            filter=Q(status__in=active_statuses, created_at__gte=current_month),
        ),
        active_prev=Sum(
            "total_amount",
            filter=Q(
                status__in=active_statuses,
                created_at__gte=previous_month,
                created_at__lt=current_month,
            ),
        ),
        active_all=Sum("total_amount", filter=Q(status__in=active_statuses)),
    )

    # default zeros
    w_cur = agg["withdraw_current"] or 0
    w_prev = agg["withdraw_prev"] or 0
    w_all = agg["withdraw_all"] or 0
    a_cur = agg["active_current"] or 0
    a_prev = agg["active_prev"] or 0
    a_all = agg["active_all"] or 0

    # Compute percentage
    def pct_change(cur, prev):
        if prev > 0:
            return (cur - prev) / prev * 100
        return 100 if cur > 0 else 0

    return {
        "withdrawable_funds": {
            "current_month": w_cur,
            "all_time": w_all,
            "percentage_change": pct_change(w_cur, w_prev),
            "is_increase": pct_change(w_cur, w_prev) >= 0,
        },
        "active_sales": {
            "current_month": a_cur,
            "all_time": a_all,
            "percentage_change": pct_change(a_cur, a_prev),
            "is_increase": pct_change(a_cur, a_prev) >= 0,
        },
    }
