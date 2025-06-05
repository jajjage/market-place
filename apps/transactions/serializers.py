# serializers.py
from rest_framework import serializers
from apps.core.serializers import TimestampedModelSerializer
from apps.products.product_base.models import Product
from apps.products.product_breadcrumb.serializers import BreadcrumbSerializer
from apps.transactions.models import EscrowTransaction, TransactionHistory
from apps.transactions.utils import breadcrumbs
from apps.transactions.utils.statuses import ESCROW_STATUSES


class ProductTrackingSerializer(TimestampedModelSerializer):
    """Simple serializer for product information in tracking context"""

    class Meta:
        model = Product
        fields = ["id", "title", "description", "price"]


class TransactionHistorySerializer(TimestampedModelSerializer):
    """Serializer for transaction history records"""

    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = TransactionHistory
        fields = ["status", "timestamp", "notes", "created_by", "created_by_name"]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return (
                f"{obj.created_by.first_name} {obj.created_by.last_name}".strip()
                or obj.created_by.email
            )
        return "System"


class EscrowTransactionShortSerializer(TimestampedModelSerializer):
    """Basic transaction info for embedding in other serializers."""

    product_title = serializers.CharField(source="product.title")
    product_image = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display")

    class Meta:
        model = EscrowTransaction
        fields = [
            "id",
            "product_title",
            "product_image",
            "amount",
            "currency",
            "status",
            "status_display",
            "created_at",
        ]

    def get_product_image(self, obj):
        return (
            obj.product.images.first().image.url
            if obj.product.images.exists()
            else None
        )


class EscrowTransactionListSerializer(TimestampedModelSerializer):
    """Serializer for listing escrow transactions"""

    product_title = serializers.CharField(source="product.title", read_only=True)
    buyer_name = serializers.SerializerMethodField()
    seller_name = serializers.SerializerMethodField()
    days_since_created = serializers.SerializerMethodField()

    class Meta:
        model = EscrowTransaction
        fields = [
            "id",
            "tracking_id",
            "product_title",
            "buyer_name",
            "seller_name",
            "status",
            "amount",
            "currency",
            "created_at",
            "days_since_created",
        ]

    def get_buyer_name(self, obj):
        if obj.buyer:
            return (
                f"{obj.buyer.first_name} {obj.buyer.last_name}".strip()
                or obj.buyer.email
            )
        return None

    def get_seller_name(self, obj):
        if obj.seller:
            return (
                f"{obj.seller.first_name} {obj.seller.last_name}".strip()
                or obj.seller.email
            )
        return None

    def get_days_since_created(self, obj):
        from django.utils import timezone

        return (timezone.now() - obj.created_at).days


class EscrowTransactionDetailSerializer(TimestampedModelSerializer):
    """Detailed serializer for escrow transactions"""

    breadcrumbs = BreadcrumbSerializer(many=True, read_only=True)
    product_details = serializers.SerializerMethodField()
    buyer_details = serializers.SerializerMethodField()
    seller_details = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    next_actions = serializers.SerializerMethodField()

    class Meta:
        model = EscrowTransaction
        fields = [
            "id",
            "tracking_id",
            "product_details",
            "buyer_details",
            "seller_details",
            "amount",
            "currency",
            "status",
            "status_display",
            "inspection_period_days",
            "inspection_end_date",
            "tracking_number",
            "shipping_carrier",
            "shipping_address",
            "notes",
            "status_changed_at",
            "is_auto_transition_scheduled",
            "auto_transition_type",
            "next_auto_transition_at",
            "created_at",
            "updated_at",
            "history",
            "next_actions",
            "breadcrumbs",
        ]

    def get_product_details(self, obj):
        return {
            "id": obj.product.id,
            "title": obj.product.title,
            "description": obj.product.description,
            "price": obj.product.price,
            "image": (
                self.context["request"].build_absolute_uri(obj.product.image.url)
                if hasattr(obj.product, "image") and obj.product.image
                else None
            ),
        }

    def get_breadcrumbs(self, obj):
        context = self.context
        return breadcrumbs(context, obj)

    def get_buyer_details(self, obj):
        if obj.buyer:
            return {
                "id": obj.buyer.id,
                "name": f"{obj.buyer.first_name} {obj.buyer.last_name}".strip() or None,
                "email": obj.buyer.email,
            }
        return None

    def get_seller_details(self, obj):
        if obj.seller:
            return {
                "id": obj.seller.id,
                "name": f"{obj.seller.first_name} {obj.seller.last_name}".strip()
                or None,
                "email": obj.seller.email,
            }
        return None

    def get_history(self, obj):
        history = TransactionHistory.objects.filter(transaction=obj).order_by(
            "timestamp"
        )
        return TransactionHistorySerializer(history, many=True).data

    def get_next_actions(self, obj):
        """Return possible next actions based on current status and user role"""
        user = self.context["request"].user
        user_type = getattr(user, "user_type", None)

        # Define possible next actions by status and role
        is_buyer = user == obj.buyer
        is_seller = user == obj.seller

        actions = {
            "initiated": {
                "BUYER": ["cancel"] if is_buyer else [],
                "SELLER": ["confirm_payment", "cancel"] if is_seller else [],
            },
            "payment_received": {"BUYER": [], "SELLER": ["ship"] if is_seller else []},
            "shipped": {
                "BUYER": ["confirm_delivery"] if is_buyer else [],
                "SELLER": [],
            },
            "delivered": {
                "BUYER": ["start_inspection"] if is_buyer else [],
                "SELLER": [],
            },
            "inspection": {
                "BUYER": ["approve", "dispute"] if is_buyer else [],
                "SELLER": [],
            },
            "disputed": {"BUYER": [], "SELLER": []},
            "completed": {"BUYER": [], "SELLER": []},
            "refunded": {"BUYER": [], "SELLER": []},
            "cancelled": {"BUYER": [], "SELLER": []},
        }

        # For staff, return all possible actions
        if user.is_staff:
            return {
                "initiated": ["confirm_payment", "cancel"],
                "payment_received": ["ship", "refund"],
                "shipped": ["confirm_delivery", "report_issue"],
                "delivered": ["start_inspection", "report_issue"],
                "inspection": ["approve", "dispute"],
                "disputed": ["resolve_for_buyer", "resolve_for_seller"],
                "completed": [],
                "refunded": [],
                "cancelled": [],
            }.get(obj.status, [])

        # For regular users, return actions based on user type
        return actions.get(obj.status, {}).get(user_type, [])


class EscrowTransactionTrackingSerializer(TimestampedModelSerializer):
    """Serializer specifically for tracking an escrow transaction"""

    product_title = serializers.CharField(source="product.title", read_only=True)
    product_image = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    status_timeline = serializers.SerializerMethodField()
    estimated_completion = serializers.SerializerMethodField()
    tracking_info = serializers.SerializerMethodField()

    class Meta:
        model = EscrowTransaction
        fields = [
            "id",
            "tracking_id",
            "product_title",
            "product_image",
            "status",
            "status_display",
            "created_at",
            "updated_at",
            "status_timeline",
            "estimated_completion",
            "tracking_info",
            "inspection_end_date",
        ]
        read_only = ["id"]

    def get_product_image(self, obj):
        if hasattr(obj.product, "image") and obj.product.image:
            return self.context["request"].build_absolute_uri(obj.product.image.url)
        return None

    def get_status_timeline(self, obj):
        """Return a timeline of status changes for tracking visualization"""
        history = TransactionHistory.objects.filter(transaction=obj).order_by(
            "timestamp"
        )
        statuses = []

        # Create a complete timeline with all possible statuses
        status_order = [status[0] for status in EscrowTransaction.STATUS_CHOICES]
        current_status_index = (
            status_order.index(obj.status) if obj.status in status_order else -1
        )

        for i, status_code in enumerate(status_order):
            # Find the history entry for this status if it exists
            entry = next((h for h in history if h.status == status_code), None)

            statuses.append(
                {
                    "code": status_code,
                    "label": dict(EscrowTransaction.STATUS_CHOICES).get(status_code),
                    "description": ESCROW_STATUSES[status_code]["description"],
                    "completed": entry is not None,
                    "active": status_code == obj.status,
                    "timestamp": entry.timestamp if entry else None,
                    "upcoming": i > current_status_index,
                }
            )

        return statuses

    def get_estimated_completion(self, obj):
        """Estimate when the transaction will be completed"""
        from django.utils import timezone
        import datetime

        # Only provide estimates for active transactions
        if obj.status in ["completed", "refunded", "cancelled", "disputed"]:
            return None

        # Based on current status, estimate days until completion
        remaining_days = {
            "initiated": 14,  # Two weeks for payment
            "payment_received": 7,  # One week for shipping
            "shipped": 5,  # Five days for delivery
            "delivered": 1,  # One day to start inspection
            "inspection": obj.inspection_period_days,  # Inspection period
        }.get(obj.status, None)

        if remaining_days is None:
            return None

        return (
            (timezone.now() + datetime.timedelta(days=remaining_days))
            .date()
            .isoformat()
        )

    def get_tracking_info(self, obj):
        """Get shipping tracking information if available"""
        if not obj.tracking_number or not obj.shipping_carrier:
            return None

        return {
            "carrier": obj.shipping_carrier,
            "tracking_number": obj.tracking_number,
            "tracking_url": self._get_tracking_url(
                obj.shipping_carrier, obj.tracking_number
            ),
        }

    def _get_tracking_url(self, carrier, tracking_number):
        """Generate tracking URL based on carrier"""
        tracking_urls = {
            "UPS": f"https://www.ups.com/track?tracknum={tracking_number}",
            "USPS": f"https://tools.usps.com/go/TrackConfirmAction?tLabels={tracking_number}",
            "FedEx": f"https://www.fedex.com/fedextrack/?trknbr={tracking_number}",
            "DHL": f"https://www.dhl.com/en/express/tracking.html?AWB={tracking_number}",
        }

        return tracking_urls.get(
            carrier.upper(), "#"
        )  # Return placeholder if carrier not recognized
