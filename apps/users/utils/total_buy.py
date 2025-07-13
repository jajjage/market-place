from django.db.models import Sum, Count, Avg, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import timedelta


def get_buyer_analytics_summary(user):
    now = timezone.now()
    # month boundaries
    start_current = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start_prev = (start_current - timedelta(days=1)).replace(day=1)

    base_qs = user.buyer_transactions.all()

    # Single‐query aggregations for spending and order‐status
    agg = base_qs.aggregate(
        # spending
        spend_curr=Sum("total_amount", filter=Q(created_at__gte=start_current)),
        spend_prev=Sum(
            "total_amount",
            filter=Q(created_at__gte=start_prev, created_at__lt=start_current),
        ),
        spend_all=Sum("total_amount"),
        orders_all=Count("id"),
        avg_order_all=Avg("total_amount"),
        # status counts & sums
        active_count=Count(
            "id", filter=Q(status__in=["payment_received", "shipped", "processing"])
        ),
        active_sum=Sum(
            "total_amount",
            filter=Q(status__in=["payment_received", "shipped", "processing"]),
        ),
        completed_count=Count("id", filter=Q(status="delivered")),
        completed_sum=Sum("total_amount", filter=Q(status="delivered")),
        pending_count=Count(
            "id", filter=Q(status__in=["pending_payment", "pending_confirmation"])
        ),
        pending_sum=Sum(
            "total_amount",
            filter=Q(status__in=["pending_payment", "pending_confirmation"]),
        ),
        cancelled_count=Count("id", filter=Q(status__in=["cancelled", "refunded"])),
        cancelled_sum=Sum(
            "total_amount", filter=Q(status__in=["cancelled", "refunded"])
        ),
    )

    # spending change
    curr_spend = agg["spend_curr"] or 0
    prev_spend = agg["spend_prev"] or 0
    if prev_spend > 0:
        spend_pct = (curr_spend - prev_spend) / prev_spend * 100
    else:
        spend_pct = 100 if curr_spend > 0 else 0

    # biggest purchase
    biggest = (
        base_qs.order_by("-total_amount").values_list("total_amount", flat=True).first()
        or 0
    )

    # purchase ranges (single extra query)
    ranges = base_qs.aggregate(
        under_50=Count("id", filter=Q(total_amount__lt=50)),
        fifty_200=Count("id", filter=Q(total_amount__gte=50, total_amount__lt=200)),
        two_hundred_500=Count(
            "id", filter=Q(total_amount__gte=200, total_amount__lt=500)
        ),
        over_500=Count("id", filter=Q(total_amount__gte=500)),
    )

    # yearly orders
    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    yearly_orders = base_qs.filter(created_at__gte=year_start).count()

    # order frequency
    first_order = (
        base_qs.order_by("created_at").values_list("created_at", flat=True).first()
    )
    months_active = max(1, (now - (first_order or now)).days / 30)
    frequency = (agg["orders_all"] or 0) / months_active

    # monthly trend last 6 months
    trend_qs = (
        base_qs.annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(
            total=Sum("total_amount"),
            count=Count("id"),
        )
        .order_by("-month")[:6]
    )
    monthly_trends = [
        {
            "month": item["month"].strftime("%B %Y"),
            "total": item["total"] or 0,
            "orders": item["count"] or 0,
        }
        for item in trend_qs
    ][
        ::-1
    ]  # reverse to chronological

    return {
        "spending_summary": {
            "current_month": curr_spend,
            "previous_month": prev_spend,
            "all_time": agg["spend_all"] or 0,
            "percentage_change": spend_pct,
            "is_increase": spend_pct >= 0,
            "avg_order_value": agg["avg_order_all"] or 0,
        },
        "order_summary": {
            "active_orders": {
                "count": agg["active_count"] or 0,
                "total_amount": agg["active_sum"] or 0,
            },
            "completed_orders": {
                "count": agg["completed_count"] or 0,
                "total_amount": agg["completed_sum"] or 0,
            },
            "pending_orders": {
                "count": agg["pending_count"] or 0,
                "total_amount": agg["pending_sum"] or 0,
            },
            "cancelled_orders": {
                "count": agg["cancelled_count"] or 0,
                "total_amount": agg["cancelled_sum"] or 0,
            },
            "total_orders": agg["orders_all"] or 0,
        },
        "insights": {
            "avg_monthly_spending": sum(m["total"] for m in monthly_trends) / 6,
            "biggest_purchase": biggest,
            "yearly_orders": yearly_orders,
            "order_frequency": frequency,
            "purchase_ranges": ranges,
        },
        "monthly_trends": monthly_trends,
    }


def get_buyer_quick_stats(user):
    # this can be pulled from the same agg if desired, but standalone:
    now = timezone.now()
    start_curr = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start_prev = (start_curr - timedelta(days=1)).replace(day=1)
    qs = user.buyer_transactions.all()

    agg = qs.aggregate(
        curr=Sum("total_amount", filter=Q(created_at__gte=start_curr)),
        prev=Sum(
            "total_amount",
            filter=Q(created_at__gte=start_prev, created_at__lt=start_curr),
        ),
        active=Count(
            "id", filter=Q(status__in=["payment_received", "shipped", "processing"])
        ),
    )

    curr = agg["curr"] or 0
    prev = agg["prev"] or 0
    if prev > 0:
        pct = (curr - prev) / prev * 100
    else:
        pct = 100 if curr > 0 else 0

    return {
        "monthly_spending": curr,
        "percentage_change": pct,
        "is_increase": pct >= 0,
        "active_orders": agg["active"] or 0,
    }
