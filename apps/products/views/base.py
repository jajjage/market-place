import urllib.parse
from datetime import timezone
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
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
from apps.products.models import (
    Product,
    ProductMeta,
    NegotiationHistory,
    PriceNegotiation,
)
from apps.products.serializers import (
    ProductCreateSerializer,
    ProductUpdateSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductStatsSerializer,
    # Uncomment the following line if you have this serializer defined
    # ProductWatchlistItemCreateSerializer,
)
from apps.products.services import InventoryService
from apps.products.utils.product_filters import ProductFilter


class ProductViewSet(BaseViewSet):
    """
    ViewSet for managing products with different serializers for different operations.
    Supports CRUD operations, filtering, searching, and statistics.
    """

    CACHE_TTL = 60 * 15  # 15 minutes cache
    STATS_CACHE_TTL = 60 * 30  # 30 minutes cache for stats

    queryset = Product.objects.all()
    permission_classes = [ReadWriteUserTypePermission]
    permission_read_user_types = ["BUYER", "SELLER"]
    permission_write_user_types = ["SELLER"]
    inventory_user_types = ["SELLER"]
    buyer_user_types = ["BUYER"]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = ProductFilter
    search_fields = ["title", "description", "slug", "short_code"]
    ordering_fields = ["price", "created_at", "title", "inventory_count"]
    ordering = ["-created_at"]

    def get_cache_key(self, view_name, **kwargs):
        """Generate a cache key for the view"""
        return f"product:{view_name}:{kwargs.get('pk', '')}:{kwargs.get('user_id', '')}"

    def get_permissions(self):
        """
        Custom permissions:
        - List/retrieve: Both BUYER and SELLER can view products
        - Create/update/delete: Only SELLER can modify products
        - Inventory actions: Only SELLER can manage inventory
        """
        # Define inventory management actions
        inventory_actions = [
            "add_inventory",
            "activate_inventory",
            "release_from_escrow",
            "deduct_inventory",
            "respond_to_negotiation",
        ]
        buy_action = [
            "place_in_escrow",
            "create_transaction_from_negotiation",
            "initiate_negotiation",
        ]

        # Set appropriate user types based on the action
        if self.action in inventory_actions:
            # Temporarily override permission user types for inventory actions
            self.permission_write_user_types = self.inventory_user_types
        elif self.action in buy_action:
            self.permission_write_user_types = self.buyer_user_types

        # Use the standard ReadWriteUserTypePermission logic
        return [permission() for permission in self.permission_classes]

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

    @method_decorator(cache_page(CACHE_TTL))
    @method_decorator(vary_on_cookie)
    @action(detail=False, url_path="my-products", methods=["get"])
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
        return self.success_response(data=serializer.data)

    @method_decorator(cache_page(CACHE_TTL))
    @method_decorator(vary_on_cookie)
    @action(detail=False, methods=["get"])
    def featured(self, request):
        """Return featured products"""
        queryset = self.get_queryset().filter(is_featured=True, is_active=True)
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return self.success_response(data=serializer.data)

    @method_decorator(cache_page(STATS_CACHE_TTL))
    @method_decorator(vary_on_cookie)
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
            total=Sum("total_inventory"), avg_per_product=Avg("total_inventory")
        )
        # Get inventory stats
        inventory_available = queryset.aggregate(
            total=Sum("available_inventory"), avg_per_product=Avg("available_inventory")
        )
        # Get inventory stats
        inventory_in_escrow = queryset.aggregate(
            total=Sum("in_escrow_inventory"), avg_per_product=Avg("in_escrow_inventory")
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
            "categories": list(category_distribution),
            "status_distribution": list(status_distribution),
            "most_watched_products": most_watched_data,
            "monthly_trend": monthly_trend_data,
        }

        return self.success_response(data=stats_data)

    def perform_update(self, serializer):
        """Clear cache when product is updated"""
        product = serializer.instance
        cache_keys = [
            self.get_cache_key("detail", pk=product.pk),
            self.get_cache_key("list"),
            "featured_products",
            f"product_stats:{product.seller.id}",
        ]
        cache.delete_many(cache_keys)
        return super().perform_update(serializer)

    def perform_destroy(self, instance):
        """Clear cache when product is deleted"""
        cache_keys = [
            self.get_cache_key("detail", pk=instance.pk),
            self.get_cache_key("list"),
            "featured_products",
            f"product_stats:{instance.seller.id}",
        ]
        cache.delete_many(cache_keys)
        return super().perform_destroy(instance)

    @action(detail=True, url_path="toggle-active", methods=["post"])
    def toggle_active(self, request, pk=None):
        """Quickly toggle the active status of a product"""
        product = self.get_object()
        product.is_active = not product.is_active
        product.save()

        # Clear relevant caches
        cache_keys = [
            self.get_cache_key("detail", pk=product.pk),
            self.get_cache_key("list"),
            "featured_products",
            f"product_stats:{product.seller.id}",
        ]
        cache.delete_many(cache_keys)

        return self.success_response(data=product.is_active)

    @action(detail=True, url_path="toggle-featured", methods=["post"])
    def toggle_featured(self, request, pk=None):
        """Quickly toggle the featured status of a product"""
        product = self.get_object()
        product.is_featured = not product.is_featured
        product.save()

        # Clear relevant caches
        cache_keys = [
            self.get_cache_key("detail", pk=product.pk),
            self.get_cache_key("list"),
            "featured_products",
            f"product_stats:{product.seller.id}",
        ]
        cache.delete_many(cache_keys)

        return self.success_response(data=product.is_featured)

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

        return self.success_response(data=share_links)

    @action(detail=True, url_path="add-inventory", methods=["post"])
    def add_inventory(self, request, pk=None):
        """Add inventory to total"""
        product = self.get_object()
        if not product.is_active:
            return self.error_response(
                message="Cannot add inventory to inactive product",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        quantity = request.data.get("quantity", 1)
        notes = request.data.get("notes", "")

        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValueError("Quantity must be positive and Product must be active")
        except (ValueError, TypeError):
            return self.error_response(
                message="Invalid quantity",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        result = InventoryService.add_inventory(
            product=product, quantity=quantity, user=request.user, notes=notes
        )

        if result:
            return Response(
                {
                    "status": "success",
                    "total": result.total_inventory,
                    "available": result.available_inventory,
                    "in_escrow": result.in_escrow_inventory,
                }
            )
        else:
            return Response(
                {"status": "error", "message": "Failed to add inventory"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, url_path="activate-inventory", methods=["post"])
    def activate_inventory(self, request, pk=None):
        """Move inventory from total to available"""
        product = self.get_object()
        if not product.is_active:
            return self.error_response(
                message="Cannot activate inventory to inactive product",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        quantity = request.data.get("quantity")
        notes = request.data.get("notes", "")

        if quantity is not None:
            try:
                quantity = int(quantity)
                if quantity <= 0:
                    raise ValueError("Quantity must be positive")
            except (ValueError, TypeError):
                return Response(
                    {"status": "error", "message": "Invalid quantity"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        result = InventoryService.activate_inventory(
            product=product, quantity=quantity, user=request.user, notes=notes
        )

        if result:
            return Response(
                {
                    "status": "success",
                    "total": result.total_inventory,
                    "available": result.available_inventory,
                    "in_escrow": result.in_escrow_inventory,
                }
            )
        else:
            return Response(
                {"status": "error", "message": "No inventory to activate"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, url_path="place-in-escrow", methods=["post"])
    def place_in_escrow(self, request, pk=None):
        """Place inventory in escrow for transaction"""
        product = self.get_object()
        if not product.is_active:
            return self.error_response(
                message="Cannot place escrow to inactive product",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        quantity = request.data.get("quantity", 1)
        notes = request.data.get("notes", "")

        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValueError("Quantity must be positive")
        except (ValueError, TypeError):
            return Response(
                {"status": "error", "message": "Invalid quantity"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = InventoryService.place_in_escrow(
            product=product, quantity=quantity, buyer=request.user, notes=notes
        )

        product_result = result[0]
        transaction_tracking_id = result[1]

        if result:
            return Response(
                {
                    "status": "success",
                    "total": product_result.total_inventory,
                    "available": product_result.available_inventory,
                    "in_escrow": product_result.in_escrow_inventory,
                    "transaction_id": transaction_tracking_id.tracking_id,
                }
            )
        else:
            return Response(
                {"status": "error", "message": "Insufficient available inventory"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, url_path="release-from-escrow", methods=["post"])
    def release_from_escrow(self, request, pk=None):
        """Release inventory from escrow back to available"""
        product = self.get_object()
        if not product.is_active:
            return self.error_response(
                message="Cannot release from escrow to inactive product",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        quantity = request.data.get("quantity", 1)
        notes = request.data.get("notes", "")

        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValueError("Quantity must be positive")
        except (ValueError, TypeError):
            return Response(
                {"status": "error", "message": "Invalid quantity"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = InventoryService.release_from_escrow(
            product=product, quantity=quantity, user=request.user, notes=notes
        )

        if result:
            return Response(
                {
                    "status": "success",
                    "total": result.total_inventory,
                    "available": result.available_inventory,
                    "in_escrow": result.in_escrow_inventory,
                }
            )
        else:
            return Response(
                {"status": "error", "message": "Insufficient inventory in escrow"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, url_path="deduct-inventory", methods=["post"])
    def deduct_inventory(self, request, pk=None):
        """Deduct inventory from escrow (completing a sale)"""
        product = self.get_object()
        if not product.is_active:
            return self.error_response(
                message="Cannot deduct inventory to inactive product",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        quantity = request.data.get("quantity", 1)
        notes = request.data.get("notes", "")

        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValueError("Quantity must be positive")
        except (ValueError, TypeError):
            return Response(
                {"status": "error", "message": "Invalid quantity"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = InventoryService.deduct_inventory(
            product=product, quantity=quantity, user=request.user, notes=notes
        )

        if result:
            return Response(
                {
                    "status": "success",
                    "total": result.total_inventory,
                    "available": result.available_inventory,
                    "in_escrow": result.in_escrow_inventory,
                }
            )
        else:
            return Response(
                {"status": "error", "message": "Failed to deduct inventory"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, url_path=r"initiate-negotiation", methods=["post"])
    def initiate_negotiation(self, request, pk=None):
        """
        Initiate a price negotiation for a product.
        This endpoint allows buyers to submit an offer for a product before creating a transaction.
        The product must have the 'is_negotiable' flag set to True.
        """
        # Find the product
        product = self.get_object()

        # Check if the product is negotiable
        if not product.is_negotiable:
            return Response(
                {"detail": "This product does not allow price negotiation."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if user is authenticated
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication required to negotiate price."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Check if user is not the seller
        if request.user == product.seller:
            return Response(
                {"detail": "You cannot negotiate price for your own product."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get and validate the offered price
        try:
            offered_price = request.data.get("offered_price")
            if offered_price is None:
                return Response(
                    {"detail": "Offered price is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            offered_price = float(offered_price)

            # Optional: Business validation rules
            if offered_price <= 0:
                return Response(
                    {"detail": "Offered price must be greater than zero."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Optional: Minimum offer amount (e.g., at least 50% of original price)
            min_acceptable = float(product.price) * 0.5
            if offered_price < min_acceptable:
                return Response(
                    {
                        "detail": f"Offered price is too low. Minimum acceptable is ${min_acceptable:.2f}."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check for existing active negotiations
            existing_negotiation = PriceNegotiation.objects.filter(
                product=product, buyer=request.user, status__in=["pending", "countered"]
            ).first()

            if existing_negotiation:
                # Update existing negotiation
                existing_negotiation.offered_price = offered_price
                existing_negotiation.status = "pending"
                existing_negotiation.updated_at = timezone.now()
                existing_negotiation.save()

                negotiation = existing_negotiation
                created = False
            else:
                # Create new negotiation
                negotiation = PriceNegotiation.objects.create(
                    product=product,
                    buyer=request.user,
                    seller=product.seller,
                    original_price=product.price,
                    offered_price=offered_price,
                    status="pending",
                    offered_at=timezone.now(),
                )
                created = True

            # Record in history
            NegotiationHistory.objects.create(
                negotiation=negotiation,
                action="price_offered",
                user=request.user,
                price=offered_price,
                notes=f"Buyer offered ${offered_price:.2f} for the product",
            )

            # Notify seller about the new offer
            # Implementation depends on your notification system
            # notify_seller(product.seller, product, offered_price, request.user)

            return Response(
                {
                    "detail": "Your offer has been submitted successfully.",
                    "negotiation_id": negotiation.id,
                    "product": {
                        "id": product.id,
                        "name": product.name,
                        "original_price": float(product.price),
                    },
                    "offered_price": offered_price,
                    "status": negotiation.status,
                    "seller": negotiation.seller.username,
                    "created_at": negotiation.offered_at,
                },
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )

        except ValueError:
            return Response(
                {"detail": "Invalid price format."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {
                    "detail": f"An error occurred while processing your request: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(
        detail=False,
        url_path=r"respond-to-negotiation/(?P<negotiation_id>[^/.]+)",
        methods=["post"],
    )
    def respond_to_negotiation(self, request, negotiation_id=None):
        """
        Respond to a price negotiation offer.
        This endpoint allows sellers to accept, reject, or counter a buyer's offer.
        """
        # Find the negotiation
        negotiation = get_object_or_404(PriceNegotiation, id=negotiation_id)

        # Check if user is the seller
        if request.user != negotiation.seller:
            return Response(
                {"detail": "Only the seller can respond to this negotiation."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check if negotiation is in a valid state to respond
        if negotiation.status not in ["pending", "countered"]:
            return Response(
                {
                    "detail": f"Cannot respond to a negotiation with status '{negotiation.status}'."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the response type and validate
        response_type = request.data.get("response_type")
        if response_type not in ["accept", "reject", "counter"]:
            return Response(
                {"detail": "Response type must be 'accept', 'reject', or 'counter'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            if response_type == "accept":
                # Accept the offered price
                negotiation.status = "accepted"
                negotiation.final_price = negotiation.offered_price
                negotiation.save()

                # Record in history
                NegotiationHistory.objects.create(
                    negotiation=negotiation,
                    action="price_accepted",
                    user=request.user,
                    price=negotiation.offered_price,
                    notes=f"Seller accepted the offered price of ${float(negotiation.offered_price):.2f}",
                )

                # If there's already a transaction linked, update its price
                if negotiation.transaction:
                    transaction = negotiation.transaction
                    transaction.price_by_negotiation = negotiation.final_price
                    transaction.save()

                message = "You have accepted the buyer's offer."
                action = "accepted"

            elif response_type == "reject":
                # Reject the offered price
                negotiation.status = "rejected"
                negotiation.save()

                # Record in history
                NegotiationHistory.objects.create(
                    negotiation=negotiation,
                    action="price_rejected",
                    user=request.user,
                    price=negotiation.offered_price,
                    notes=f"Seller rejected the offered price of ${float(negotiation.offered_price):.2f}",
                )

                message = "You have rejected the buyer's offer."
                action = "rejected"

            elif response_type == "counter":
                # Counter offer with a new price
                counter_price = request.data.get("counter_price")
                if counter_price is None:
                    return Response(
                        {"detail": "Counter price is required for a counter offer."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                counter_price = float(counter_price)

                # Validate counter price is reasonable
                if counter_price <= 0:
                    return Response(
                        {"detail": "Counter price must be greater than zero."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if counter_price <= float(negotiation.offered_price):
                    return Response(
                        {
                            "detail": "Counter price should be higher than the buyer's offer."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if counter_price > float(negotiation.original_price):
                    return Response(
                        {
                            "detail": "Counter price cannot be higher than the original price."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Update negotiation
                negotiation.status = "countered"
                # Store the counter price in offered_price for history reference
                previous_offer = negotiation.offered_price
                negotiation.offered_price = counter_price
                negotiation.save()

                # Record in history
                NegotiationHistory.objects.create(
                    negotiation=negotiation,
                    action="price_countered",
                    user=request.user,
                    price=counter_price,
                    notes=f"Seller counter-offered ${counter_price:.2f} to the buyer's offer of ${float(previous_offer):.2f}",
                )

                message = f"You have counter-offered ${counter_price:.2f} to the buyer."
                action = "countered"

            # Notify the buyer about the seller's response
            # Implementation depends on your notification system
            # notify_buyer(negotiation.buyer, negotiation.product, action, request.user)

            return Response(
                {
                    "detail": message,
                    "negotiation_id": negotiation.id,
                    "product": {
                        "id": negotiation.product.id,
                        "name": negotiation.product.name,
                    },
                    "status": negotiation.status,
                    "original_price": float(negotiation.original_price),
                    "buyer_offer": float(
                        previous_offer
                        if response_type == "counter"
                        else negotiation.offered_price
                    ),
                    "final_price": (
                        float(negotiation.final_price)
                        if negotiation.final_price
                        else None
                    ),
                    "counter_price": (
                        counter_price if response_type == "counter" else None
                    ),
                    "buyer": negotiation.buyer.username,
                },
                status=status.HTTP_200_OK,
            )

        except ValueError:
            return Response(
                {"detail": "Invalid price format."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {
                    "detail": f"An error occurred while processing your request: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(
        detail=False,
        url_path=r"create-transaction/(?P<negotiation_id>[^/.]+)",
        methods=["post"],
    )
    def create_transaction_from_negotiation(self, request, negotiation_id=None):
        """
        Create an escrow transaction from an accepted negotiation.
        This endpoint allows buyers to proceed with purchase after a successful negotiation.
        """
        # Find the negotiation
        negotiation = get_object_or_404(PriceNegotiation, id=negotiation_id)
        quantity = request.data.get("quantity", 1)
        notes = request.data.get("notes", "")

        # Check if user is the buyer
        if request.user != negotiation.buyer:
            return Response(
                {
                    "detail": "Only the buyer can create a transaction from this negotiation."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check if negotiation is accepted
        if negotiation.status != "accepted":
            return Response(
                {
                    "detail": f"Cannot create transaction for a negotiation with status '{negotiation.status}'. Only accepted negotiations can proceed to transaction."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if a transaction already exists for this negotiation
        if negotiation.transaction:
            return Response(
                {"detail": "A transaction already exists for this negotiation."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            product = negotiation.product
            final_price = negotiation.final_price

            result = InventoryService.place_in_escrow(
                product=product,
                quantity=quantity,
                buyer=request.user,
                price_by_negotiation=final_price,
                amount=product.price,
                notes=notes,
            )

            product_result = result[0]
            transaction = result[1]

            # Link the transaction to the negotiation
            negotiation.transaction = transaction
            negotiation.save()

            if result:
                # Notify the seller about the new transaction
                # Implementation depends on your notification system
                # notify_seller(transaction.seller, transaction, request.user)

                return Response(
                    {
                        "detail": "Transaction created successfully from your negotiation.",
                        "transaction_id": transaction.id,
                        "tracking_id": transaction.tracking_id,
                        "product": {
                            "id": product_result.id,
                            "name": product_result.title,
                        },
                        "original_price": float(product_result.price),
                        "negotiated_price": float(final_price),
                        "status": transaction.status,
                        "seller": transaction.seller.email,
                    },
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response(
                    {"status": "error", "message": "Insufficient available inventory"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except Exception as e:
            return Response(
                {
                    "detail": f"An error occurred while processing your request: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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

    @method_decorator(cache_page(60 * 5))  # Cache for 5 minutes
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
