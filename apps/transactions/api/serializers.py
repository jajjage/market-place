from rest_framework import serializers
from apps.core.serializers import TimestampedModelSerializer
from apps.core.utils.breadcrumbs import BreadcrumbService
from apps.core.serializers import BreadcrumbSerializer
from apps.products.product_base.models import Product
from apps.products.product_image.services import ProductImageService
from apps.transactions.models import EscrowTransaction, TransactionHistory


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
        fields = [
            "timestamp",
            "notes",
            "previous_status",
            "new_status",
            "created_by",
            "created_by_name",
        ]

    def get_created_by_name(self, obj) -> str:
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
    amount = serializers.SerializerMethodField()

    class Meta:
        model = EscrowTransaction
        fields = [
            "id",
            "product_title",
            "product_image",
            "amount",
            "quantity",
            "currency",
            "status",
            "created_at",
        ]

    def get_product_image(self, obj) -> str | None:
        return (
            obj.product.images.first().image.url
            if obj.product.images.exists()
            else None
        )

    def get_amount(self, obj) -> float:
        return obj.price if obj.price else 0


class EscrowTransactionListSerializer(TimestampedModelSerializer):
    """Serializer for listing escrow transactions"""

    product_title = serializers.CharField(source="product.title", read_only=True)
    buyer_name = serializers.SerializerMethodField()
    seller_name = serializers.SerializerMethodField()
    days_since_created = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()
    # amount = serializers.SerializerMethodField()

    class Meta:
        model = EscrowTransaction
        fields = [
            "id",
            "tracking_id",
            "product_title",
            "buyer_name",
            "seller_name",
            "status",
            "quantity",
            "price",
            "total_amount",
            "currency",
            "created_at",
            "days_since_created",
            "history",
        ]

    def get_buyer_name(self, obj) -> str | None:
        if obj.buyer:
            return (
                f"{obj.buyer.first_name} {obj.buyer.last_name}".strip()
                or obj.buyer.email
            )
        return None

    def get_seller_name(self, obj) -> str | None:
        if obj.seller:
            return (
                f"{obj.seller.first_name} {obj.seller.last_name}".strip()
                or obj.seller.email
            )
        return None

    def get_days_since_created(self, obj) -> int:
        from django.utils import timezone

        return (timezone.now() - obj.created_at).days

    # def get_amount(self, obj):
    #     print(obj.price)
    #     return obj.price if obj.price else 0

    def get_history(self, obj) -> list:
        # obj.all_history is the full, prefetched, ordered history list
        latest_five = getattr(obj, "all_history", [])[:5]
        return TransactionHistorySerializer(
            latest_five, many=True, context=self.context
        ).data


class EscrowTransactionDetailSerializer(TimestampedModelSerializer):
    """Detailed serializer for escrow transactions"""

    breadcrumbs = serializers.SerializerMethodField()
    product_details = serializers.SerializerMethodField()
    variant_details = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    buyer_details = serializers.SerializerMethodField()
    seller_details = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()
    # price = serializers.SerializerMethodField()
    # total_amount = serializers.SerializerMethodField()
    # next_actions = serializers.SerializerMethodField()

    class Meta:
        model = EscrowTransaction
        fields = [
            "id",
            "tracking_id",
            "image",
            "product_details",
            "variant_details",
            "buyer_details",
            "seller_details",
            "price",
            "total_amount",
            "currency",
            "quantity",
            "status",
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
            "history",
            # "next_actions",
            "breadcrumbs",
        ]

    def get_product_details(self, obj) -> dict:
        product = obj.product
        return {
            "id": product.id,
            "title": product.title,
            "short_code": product.short_code,
            "price": product.price,
        }

    def get_variant_details(self, obj) -> dict:
        variant = obj.variant
        return {
            "id": variant.id,
            "title": variant.sku,
            "price": variant.price,
        }

    def get_image(self, obj) -> dict | None:
        request = self.context.get("request")
        if hasattr(obj.product, "images") and obj.product.images:
            primary_image = ProductImageService.get_primary_image(obj.product.id)
            if primary_image and primary_image.image_url:
                # Try to build absolute URL if request is available
                if request:
                    return {
                        "id": obj.product.id,
                        "title": obj.product.title,
                        "description": obj.product.description,
                        "price": obj.product.price,
                        "image": request.build_absolute_uri(primary_image.image_url),
                    }

                else:
                    # Fallback to relative URL or build manually
                    return {
                        "id": obj.product.id,
                        "title": obj.product.title,
                        "description": obj.product.description,
                        "price": obj.product.price,
                        "image": None,
                    }
        return None

    def get_breadcrumbs(self, obj) -> list:
        breadcrumb_data = BreadcrumbService.generate_transaction_breadcrumbs(obj)
        return BreadcrumbSerializer(breadcrumb_data, many=True).data

    def get_buyer_details(self, obj) -> dict | None:
        if obj.buyer:
            return {
                "id": obj.buyer.id,
                "name": f"{obj.buyer.first_name} {obj.buyer.last_name}".strip() or None,
                "email": obj.buyer.email,
            }
        return None

    def get_seller_details(self, obj) -> dict | None:
        if obj.seller:
            return {
                "id": obj.seller.id,
                "name": f"{obj.seller.first_name} {obj.seller.last_name}".strip()
                or None,
                "email": obj.seller.email,
            }
        return None

    def get_history(self, obj) -> list:
        history = TransactionHistory.objects.filter(transaction=obj).order_by(
            "timestamp"
        )
        return TransactionHistorySerializer(history, many=True).data


class EscrowTransactionTrackingSerializer(TimestampedModelSerializer):
    """Serializer specifically for tracking an escrow transaction"""

    product_title = serializers.CharField(source="product.title", read_only=True)
    image_url = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    estimated_completion = serializers.SerializerMethodField()
    tracking_info = serializers.SerializerMethodField()

    class Meta:
        model = EscrowTransaction
        fields = [
            "id",
            "tracking_id",
            "product_title",
            "image_url",
            "status",
            "status_display",
            "created_at",
            "updated_at",
            "estimated_completion",
            "tracking_info",
            "inspection_end_date",
        ]
        read_only = ["id"]

    def get_image_url(self, obj) -> str | None:
        request = self.context.get("request")

        if hasattr(obj.product, "images") and obj.product.images:
            primary_image = ProductImageService.get_primary_image(obj.product.id)

            if primary_image and primary_image.image_url:
                # Try to build absolute URL if request is available
                if request:
                    return request.build_absolute_uri(primary_image.image_url)
                else:
                    # Fallback to relative URL or build manually
                    return primary_image.image_url
                    # Or build manually: f"http://your-domain.com{primary_image.image_url}"

        return None

    def get_estimated_completion(self, obj) -> str | None:
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

    def get_tracking_info(self, obj) -> dict | None:
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

    def _get_tracking_url(self, carrier, tracking_number) -> str:
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


class TransactionActionSerializer(serializers.Serializer):
    """Serializer for transaction action responses"""

    status = serializers.CharField()
    requires_tracking = serializers.BooleanField()
    has_time_limit = serializers.BooleanField()
    description = serializers.CharField()

    class Meta:
        fields = ["status", "requires_tracking", "has_time_limit", "description"]


class AvailableActionsResponseSerializer(serializers.Serializer):
    """Serializer for available actions response"""

    available_actions = TransactionActionSerializer(many=True)
    user_role = serializers.CharField()
    current_status = serializers.CharField()
    transaction_info = serializers.DictField()
    status_metadata = serializers.DictField()

    class Meta:
        fields = [
            "available_actions",
            "user_role",
            "current_status",
            "transaction_info",
            "status_metadata",
        ]
