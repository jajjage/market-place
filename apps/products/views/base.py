import urllib.parse
from django.shortcuts import get_object_or_404
from django.urls import reverse

from django.db.models import Value
from django.db.models.functions import Concat
from rest_framework import permissions, status, filters, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Avg, Sum, F, ExpressionWrapper, FloatField
from django.db.models.functions import TruncMonth
from django_filters.rest_framework import DjangoFilterBackend
from apps.core.permissions import ReadWriteUserTypePermission
from apps.core.views import BaseViewSet
from apps.products.models import Product, ProductMeta
from apps.products.serializers import (
    ProductCreateSerializer,
    ProductUpdateSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductStatsSerializer,
    # Uncomment the following line if you have this serializer defined
    # ProductWatchlistItemCreateSerializer,
)
from apps.products.utils.product_filters import ProductFilter


class ProductViewSet(BaseViewSet):
    """
    ViewSet for managing products with different serializers for different operations.
    Supports CRUD operations, filtering, searching, and statistics.
    """

    queryset = Product.objects.all()
    permission_read_user_types = ["BUYER", "SELLER"]
    permission_write_user_types = ["SELLER"]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = ProductFilter
    search_fields = ["title", "description", "slug", "short_code"]
    ordering_fields = ["price", "created_at", "title", "inventory_count"]
    ordering = ["-created_at"]

    def get_permissions(self):
        """
        Custom permissions:
        - List/retrieve: Anyone can view product conditions
        - Create/update/delete: Only staff/admin users
        """
        if self.action in ["list", "retrieve"]:
            permission_classes = [ReadWriteUserTypePermission]
        else:
            permission_classes = [ReadWriteUserTypePermission]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        """
        Return different serializers based on the action.
        - create: Minimal serializer requiring only title
        - update/partial_update: Serializer for updating product details
        - list: Optimized serializer for listing products
        - retrieve: Detailed serializer with all information
        - stats: Specialized serializer for statistics
        """
        if self.action == "create":
            return ProductCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return ProductUpdateSerializer
        elif self.action == "list":
            return ProductListSerializer
        elif self.action == "stats":
            return ProductStatsSerializer
        return ProductDetailSerializer

    def get_queryset(self):
        """
        Filter queryset based on user permissions.
        - Staff can see all products
        - Normal users can only see their own products
        - Everyone can see active products in list view
        """
        queryset = super().get_queryset()

        # For list action, show only active products to non-staff
        if self.action == "list" and not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)

        # For detail, update, delete: only owner or staff can access
        elif self.action in ["retrieve", "update", "partial_update", "destroy"]:
            if not self.request.user.is_staff:
                queryset = queryset.filter(seller=self.request.user)

        # For other actions like create or custom actions, the base queryset is used

        return queryset

    @action(detail=False, methods=["get"])
    def my_products(self, request):
        """
        Return only the current user's products.
        Allows filtering by status for better management.
        """
        queryset = self.get_queryset().filter(seller=request.user)

        # Filter by status if provided
        status_param = request.query_params.get("status", None)
        if status_param:
            queryset = queryset.filter(status=status_param)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def featured(self, request):
        """Return featured products"""
        queryset = self.get_queryset().filter(is_featured=True, is_active=True)
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """
        Provide statistics for products.
        - For staff: all products stats
        - For users: their own products stats
        """
        if request.user.is_staff:
            queryset = Product.objects.all()
        else:
            queryset = Product.objects.filter(seller=request.user)

        # Get basic stats
        total_count = queryset.count()
        active_count = queryset.filter(is_active=True).count()
        featured_count = queryset.filter(is_featured=True).count()

        # Get inventory stats
        inventory_total = queryset.aggregate(
            total=Sum("inventory_count"), avg_per_product=Avg("inventory_count")
        )

        # Get category distribution
        category_distribution = (
            queryset.values("category__name")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Get status distribution
        status_distribution = (
            queryset.values("status").annotate(count=Count("id")).order_by("-count")
        )

        # Get products with discounts
        discounted_products = queryset.filter(
            original_price__isnull=False, price__lt=F("original_price")
        ).count()

        # Calculate average discount
        discounted_queryset = queryset.filter(
            original_price__isnull=False, price__lt=F("original_price")
        )
        avg_discount_percent = discounted_queryset.annotate(
            discount_pct=ExpressionWrapper(
                (F("original_price") - F("price")) * 100 / F("original_price"),
                output_field=FloatField(),
            )
        ).aggregate(avg=Avg("discount_pct"))

        # Get watchlist stats
        most_watched = queryset.annotate(watch_count=Count("watchers")).order_by(
            "-watch_count"
        )[:5]

        most_watched_data = ProductStatsSerializer(
            most_watched, many=True, context={"request": request}
        ).data

        # Monthly product creation trend
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

        stats_data = {
            "overview": {
                "total_products": total_count,
                "active_products": active_count,
                "featured_products": featured_count,
                "products_with_discount": discounted_products,
                "avg_discount_percent": round(avg_discount_percent["avg"] or 0, 1),
            },
            "inventory": {
                "total_inventory": inventory_total["total"] or 0,
                "avg_inventory_per_product": round(
                    inventory_total["avg_per_product"] or 0, 1
                ),
            },
            "categories": list(category_distribution),
            "status_distribution": list(status_distribution),
            "most_watched_products": most_watched_data,
            "monthly_trend": monthly_trend_data,
        }

        return Response(stats_data)

    @action(detail=True, methods=["post"])
    def toggle_active(self, request, pk=None):
        """Quickly toggle the active status of a product"""
        product = self.get_object()
        product.is_active = not product.is_active
        product.save()
        return Response({"status": "success", "is_active": product.is_active})

    @action(detail=True, methods=["post"])
    def toggle_featured(self, request, pk=None):
        """Quickly toggle the featured status of a product"""
        product = self.get_object()
        product.is_featured = not product.is_featured
        product.save()
        return Response({"status": "success", "is_featured": product.is_featured})

    @action(detail=True, methods=["get"])
    def watchers(self, request, pk=None):
        """Get statistics about users watching this product"""
        product = self.get_object()

        # Check permissions - only allow owner or staff
        if product.seller != request.user and not request.user.is_staff:
            return Response(
                {"detail": "You do not have permission to view this information."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get all watchers (without revealing sensitive information)
        watchers = product.watchers.select_related("user")

        watcher_data = {
            "count": watchers.count(),
            "recent_additions": (
                watchers.annotate(
                    full_name=Concat("user__first_name", Value(" "), "user__last_name")
                )
                .order_by("-added_at")[:5]
                .values("user_id", "user__email", "full_name", "added_at"),
            ),
        }

        return self.success_response(data=watcher_data)

    @action(
        detail=False, url_path=r"share-links/(?P<short_code>[^/.]+)", methods=["get"]
    )
    def get_share_links(self, request, short_code=None):
        """
        Generate shareable links for various social media platforms.
        """
        # 1) Fetch by short_code, not by pk
        product = get_object_or_404(Product, short_code=short_code)

        # 2) Create/Get meta and bump total_shares
        meta, _ = ProductMeta.objects.get_or_create(product=product)

        # 1) Increment total_shares
        meta.total_shares = F("total_shares") + 1
        meta.save(update_fields=["total_shares"])

        # 2) Fire analytics event
        # analytics.track(
        #     event="Share Links Generated",
        #     product_id=product.id,
        #     short_code=product.short_code,
        #     request=request,
        # )

        # 3) Build absolute product URL
        product_path = reverse("product-detail-by-shortcode", args=[product.short_code])
        product_url = request.build_absolute_uri(product_path)

        # 4) URL-encode title and URL
        url_enc = urllib.parse.quote_plus(product_url)
        title_enc = urllib.parse.quote_plus(product.title)

        share_links = {
            "direct": product_url,
            "facebook": f"https://www.facebook.com/sharer/sharer.php?u={url_enc}&ref=facebook",
            "twitter": f"https://twitter.com/intent/tweet?url={url_enc}&text={title_enc}&ref=twitter",
            "whatsapp": f"https://wa.me/?text={title_enc}%20-%20{url_enc}&ref=whatsapp",
            "linkedin": f"https://www.linkedin.com/sharing/share-offsite/?url={url_enc}&ref=linkedin",
            "telegram": f"https://t.me/share/url?url={url_enc}&text={title_enc}&ref=telegram",
        }

        return Response({"share_urls": share_links})


# Product retrieval by short code for social media sharing
class ProductDetailByShortCode(generics.RetrieveAPIView):
    """
    Retrieve a product by its short code.
    Used for both viewing and sharing via short URLs.
    """

    queryset = Product.objects.all()
    serializer_class = ProductDetailSerializer
    lookup_field = "short_code"
    permission_classes = [permissions.AllowAny]

    def retrieve(self, request, *args, **kwargs):
        product = self.get_object()
        meta, _ = ProductMeta.objects.get_or_create(product=product)

        print(meta)

        # 1) Handle share tracking if ?ref=<network> is present
        ref = request.query_params.get("ref")
        if ref in {"facebook", "twitter", "instagram"}:
            # increment a single counter
            meta.total_shares = F("total_shares") + 1
            meta.save(update_fields=["total_shares"])
            # fire off an analytics event
            # analytics.track(
            #     event="Product Shared",
            #     product_id=product.id,
            #     network=ref,
            #     short_code=product.short_code,
            #     request=request,
            # )

        # 2) Always increment view count on each retrieval
        meta.views_count = F("views_count") + 1
        meta.save(update_fields=["views_count"])

        # 3) Serialize product
        serializer = self.get_serializer(product)
        data = serializer.data

        # 4) Attach a map of “share URLs” for each social network
        base_url = request.build_absolute_uri(
            reverse("product-detail-by-shortcode", args=[product.short_code])
        )
        data["share_urls"] = {
            net: f"{base_url}?ref={net}" for net in ("facebook", "twitter", "instagram")
        }

        return Response(data)
