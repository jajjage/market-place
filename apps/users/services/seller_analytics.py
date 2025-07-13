from django.db.models import Sum, Count, Avg, Q
from django.db.models.functions import TruncMonth, ExtractWeekDay
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import calendar


class SellerAnalyticsService:
    """
    Optimized seller analytics: most metrics come from 1–3 queries
    instead of dozens.
    """

    def __init__(self, user):
        now = timezone.now()
        self.user = user
        self.qs = user.seller_transactions.all()
        # boundaries
        self.start_current = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        self.start_prev = (self.start_current - timedelta(days=1)).replace(day=1)
        self.start_quarter = self.start_current - timedelta(days=90)
        self.start_year = now.replace(
            month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
        self.active_statuses = ["payment_received", "shipped", "delivered"]

    def get_comprehensive_seller_analytics(self):
        return {
            "revenue_analytics": self._revenue_analytics(),
            "order_analytics": self._order_analytics(),
            "product_performance": self._product_performance(),
            "customer_analytics": self._customer_analytics(),
            "financial_health": self._financial_health(),
            "operational_metrics": self._operational_metrics(),
            "growth_metrics": self._growth_metrics(),
            "seasonal_trends": self._seasonal_trends(),
        }

    def _revenue_analytics(self):
        agg = self.qs.aggregate(
            # revenue by period
            curr=Sum(
                "total_amount",
                filter=Q(
                    status__in=self.active_statuses, created_at__gte=self.start_current
                ),
            ),
            prev=Sum(
                "total_amount",
                filter=Q(
                    status__in=self.active_statuses,
                    created_at__gte=self.start_prev,
                    created_at__lt=self.start_current,
                ),
            ),
            quarter=Sum(
                "total_amount",
                filter=Q(
                    status__in=self.active_statuses, created_at__gte=self.start_quarter
                ),
            ),
            year=Sum(
                "total_amount",
                filter=Q(
                    status__in=self.active_statuses, created_at__gte=self.start_year
                ),
            ),
            # counts
            cnt_year=Count(
                "id",
                filter=Q(
                    status__in=self.active_statuses, created_at__gte=self.start_year
                ),
            ),
            # withdrawable & pending
            withdraw=Sum("total_amount", filter=Q(status="funds_released")),
            pending=Sum("total_amount", filter=Q(status__in=self.active_statuses)),
        )
        curr = agg["curr"] or 0
        prev = agg["prev"] or 0
        growth = ((curr - prev) / prev * 100) if prev else (100 if curr else 0)
        # avg order values
        count_curr = (
            self.qs.filter(
                status__in=self.active_statuses, created_at__gte=self.start_current
            ).count()
            or 1
        )
        count_prev = (
            self.qs.filter(
                status__in=self.active_statuses,
                created_at__gte=self.start_prev,
                created_at__lt=self.start_current,
            ).count()
            or 1
        )
        aov_curr = curr / count_curr
        aov_prev = prev / count_prev
        aov_change = ((aov_curr - aov_prev) / aov_prev * 100) if aov_prev else 0

        return {
            "current_month": curr,
            "previous_month": prev,
            "quarterly": agg["quarter"] or 0,
            "yearly": agg["year"] or 0,
            "withdrawable_funds": agg["withdraw"] or 0,
            "pending_revenue": agg["pending"] or 0,
            "revenue_growth": growth,
            "current_aov": aov_curr,
            "aov_change": aov_change,
            "total_transactions": agg["cnt_year"],
        }

    def _order_analytics(self):
        # Status breakdown in one query
        breakdown = list(
            self.qs.values("status").annotate(
                count=Count("id"), total=Sum("total_amount")
            )
        )

        totals = self.qs.aggregate(
            total_orders=Count("id"),
            paid=Count("id", filter=Q(status="payment_received")),
            shipped=Count("id", filter=Q(status="shipped")),
            delivered=Count("id", filter=Q(status="delivered")),
            failed=Count(
                "id", filter=Q(status__in=["cancelled", "refunded", "failed"])
            ),
            lost=Sum(
                "total_amount", filter=Q(status__in=["cancelled", "refunded", "failed"])
            ),
        )

        t = totals["total_orders"] or 1
        paid, ship, deliv = totals["paid"], totals["shipped"], totals["delivered"]
        return {
            "status_breakdown": breakdown,
            "conversion_funnel": {
                "total": t,
                "paid": paid,
                "shipped": ship,
                "delivered": deliv,
                "payment_rate": paid / t * 100,
                "fulfillment_rate": ship / paid * 100 if paid else 0,
                "delivery_rate": deliv / ship * 100 if ship else 0,
            },
            "failed_orders": {
                "count": totals["failed"],
                "lost_revenue": totals["lost"] or 0,
            },
            "success_rate": deliv / t * 100,
        }

    def _product_performance(self):
        # Example: order value buckets in one go
        buckets = self.qs.aggregate(
            under_25=Count("id", filter=Q(total_amount__lt=25)),
            mid=Count("id", filter=Q(total_amount__gte=25, total_amount__lt=100)),
            high=Count("id", filter=Q(total_amount__gte=100)),
        )
        avg_qty = self.qs.aggregate(avg=Avg("quantity"))["avg"] or 0
        return {
            "order_value_distribution": buckets,
            "average_quantity": avg_qty,
        }

    def _customer_analytics(self):
        # Transaction patterns by hour
        patterns = list(
            self.qs.annotate(hour=ExtractWeekDay("created_at"))
            .values("hour")
            .annotate(count=Count("id"))
            .order_by("hour")
        )
        return {
            "transaction_patterns": patterns,
            "peak_hours": patterns[:3],
        }

    def _financial_health(self):
        # Monthly trend and volatility with one query
        months = list(
            self.qs.annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(total=Sum("total_amount"))
            .order_by("-month")[:6]
        )
        revenues = [m["total"] or 0 for m in months]
        avg = sum(revenues) / len(revenues) if revenues else 0
        var = sum((r - avg) ** 2 for r in revenues) / len(revenues) if revenues else 0
        vol = var.sqrt()
        return {
            "total_revenue": self._revenue_analytics()["yearly"],
            "monthly_trends": [
                {"month": m["month"].strftime("%B %Y"), "revenue": m["total"] or 0}
                for m in reversed(months)
            ],
            "average_monthly_revenue": avg,
            "revenue_volatility": vol,
            "cash_flow_health": "Stable" if vol < avg * Decimal("0.3") else "Volatile",
        }

    def _operational_metrics(self):
        totals = self.qs.aggregate(
            total=Count("id"),
            success=Count("id", filter=Q(status="delivered")),
            fulfill_count=Count("id", filter=Q(status__in=["shipped", "delivered"])),
            fulfill_rev=Sum(
                "total_amount", filter=Q(status__in=["shipped", "delivered"])
            ),
        )
        days = max(1, (timezone.now() - self.start_current).days)
        return {
            "processing_efficiency": (
                totals["success"] / totals["total"] * 100 if totals["total"] else 0
            ),
            "daily_transaction_average": totals["total"] / days,
            "fulfillment_metrics": {
                "count": totals["fulfill_count"],
                "revenue": totals["fulfill_rev"] or 0,
            },
        }

    def _growth_metrics(self):
        rev = self._revenue_analytics()
        growth = (
            (rev["current_month"] - rev["previous_month"]) / rev["previous_month"] * 100
            if rev["previous_month"]
            else (100 if rev["current_month"] else 0)
        )
        return {
            "revenue_growth": rev["revenue_growth"],
            "growth_trajectory": rev,  # you can reuse or recompute as needed
        }

    def _seasonal_trends(self):
        # Yearly month & day-of-week at once
        month_perf = {
            item["month"]: {"revenue": item["revenue"], "orders": item["orders"]}
            for item in self.qs.annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(revenue=Sum("total_amount"), orders=Count("id"))
        }

        dow_perf = {
            item["dow"]: {"revenue": item["revenue"], "orders": item["orders"]}
            for item in self.qs.annotate(dow=ExtractWeekDay("created_at"))
            .values("dow")
            .annotate(revenue=Sum("total_amount"), orders=Count("id"))
        }

        return {
            "monthly_performance": {
                m.strftime("%B"): month_perf.get(m, {"revenue": 0, "orders": 0})
                for m in month_perf
            },
            "day_of_week_performance": {
                calendar.day_name[d - 1]: dow_perf.get(d, {"revenue": 0, "orders": 0})
                for d in range(1, 8)
            },
        }


# === USAGE EXAMPLES ===


def get_seller_business_intelligence(user):
    """
    Main function to get comprehensive seller analytics
    """
    analytics_service = SellerAnalyticsService(user)
    return analytics_service.get_comprehensive_seller_analytics()


def get_seller_executive_summary(user):
    """
    Executive summary for quick decision making
    """
    analytics_service = SellerAnalyticsService(user)
    full_analytics = analytics_service.get_comprehensive_seller_analytics()

    revenue = full_analytics["revenue_analytics"]
    orders = full_analytics["order_analytics"]
    growth = full_analytics["growth_metrics"]

    return {
        "key_metrics": {
            "monthly_revenue": revenue["current_month"],
            "revenue_growth": revenue["revenue_growth"],
            "total_orders": orders["conversion_funnel"]["total_orders"],
            "success_rate": orders["success_rate"],
            "withdrawable_funds": revenue["withdrawable_funds"],
            "growth_status": growth["growth_status"],
        },
        "alerts": {
            "low_conversion": orders["success_rate"] < 70,
            "declining_growth": growth["revenue_growth"] < -10,
            "high_volatility": full_analytics["financial_health"]["cash_flow_health"]
            == "Volatile",
        },
        "recommendations": _generate_recommendations(full_analytics),
    }


def _generate_recommendations(analytics_data):
    """
    AI-powered business recommendations
    """
    recommendations = []

    # Revenue recommendations
    if analytics_data["revenue_analytics"]["revenue_growth"] < 0:
        recommendations.append(
            {
                "type": "revenue",
                "priority": "high",
                "message": "Revenue declining - consider promotional campaigns or product diversification",
            }
        )

    # Conversion recommendations
    if analytics_data["order_analytics"]["success_rate"] < 70:
        recommendations.append(
            {
                "type": "conversion",
                "priority": "medium",
                "message": "Low order completion rate - review fulfillment process",
            }
        )

    # Growth recommendations
    if analytics_data["growth_metrics"]["growth_status"] == "Stable":
        recommendations.append(
            {
                "type": "growth",
                "priority": "low",
                "message": "Stable growth - explore new markets or product lines",
            }
        )

    return recommendations
