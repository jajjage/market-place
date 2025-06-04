from django.db.models import Count, Avg, Sum, F, ExpressionWrapper, FloatField
from django.db.models.functions import TruncMonth
from apps.products.product_base.models import Product
from apps.products.product_base.serializers import ProductStatsSerializer


class ProductStatsService:
    @staticmethod
    def get_stats(user):
        if user.is_staff:
            queryset = Product.objects.all()
        else:
            queryset = Product.objects.filter(seller=user)

        total_count = queryset.count()
        active_count = queryset.filter(is_active=True).count()
        featured_count = queryset.filter(is_featured=True).count()
        inventory_total = queryset.aggregate(
            total=Sum("total_inventory"), avg_per_product=Avg("total_inventory")
        )
        inventory_available = queryset.aggregate(
            total=Sum("available_inventory"), avg_per_product=Avg("available_inventory")
        )
        inventory_in_escrow = queryset.aggregate(
            total=Sum("in_escrow_inventory"), avg_per_product=Avg("in_escrow_inventory")
        )
        category_distribution = list(
            queryset.values("category__name")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        status_distribution = list(
            queryset.values("status").annotate(count=Count("id")).order_by("-count")
        )
        discounted_products = queryset.filter(
            original_price__isnull=False, price__lt=F("original_price")
        ).count()
        discounted_queryset = queryset.filter(
            original_price__isnull=False, price__lt=F("original_price")
        )
        avg_discount_percent = discounted_queryset.annotate(
            discount_pct=ExpressionWrapper(
                (F("original_price") - F("price")) * 100 / F("original_price"),
                output_field=FloatField(),
            )
        ).aggregate(avg=Avg("discount_pct"))
        most_watched = queryset.annotate(watch_count=Count("watchers")).order_by(
            "-watch_count"
        )[:5]
        most_watched_data = ProductStatsSerializer(most_watched, many=True).data
        monthly_trend = (
            queryset.annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )
        monthly_trend_data = [
            {"month": item["month"].strftime("%Y-%m"), "count": item["count"]}
            for item in monthly_trend
        ]
        return {
            "overview": {
                "total_products": total_count,
                "active_products": active_count,
                "featured_products": featured_count,
                "products_with_discount": discounted_products,
                "avg_discount_percent": round(avg_discount_percent["avg"] or 0, 1),
            },
            "total_inventory": {
                "total_inventory": inventory_total["total"] or 0,
                "avg_inventory_per_product": round(
                    inventory_total["avg_per_product"] or 0, 1
                ),
            },
            "available_inventory": {
                "total_inventory": inventory_available["total"] or 0,
                "avg_inventory_per_product": round(
                    inventory_available["avg_per_product"] or 0, 1
                ),
            },
            "in_escrow_inventory": {
                "total_inventory": inventory_in_escrow["total"] or 0,
                "avg_inventory_per_product": round(
                    inventory_in_escrow["avg_per_product"] or 0, 1
                ),
            },
            "categories": category_distribution,
            "status_distribution": status_distribution,
            "most_watched_products": most_watched_data,
            "monthly_trend": monthly_trend_data,
        }
