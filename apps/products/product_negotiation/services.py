import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from django.db import transaction, models
from django.utils import timezone
from django.conf import settings

from apps.core.utils.cache_manager import CacheKeyManager, CacheManager
from apps.products.product_negotiation.models import (
    PriceNegotiation,
    NegotiationHistory,
)
from apps.products.product_base.models import Product
from apps.users.models import CustomUser as User

logger = logging.getLogger("negotiation_performance")


class NegotiationValidationService:
    """Service for validating negotiation business rules"""

    @staticmethod
    def validate_negotiation_eligibility(
        product: Product, buyer: User
    ) -> Dict[str, any]:
        """Validate if a negotiation can be initiated"""
        start_time = timezone.now()

        errors = []

        # Check if product is negotiable
        if not product.is_negotiable:
            errors.append("This product does not allow price negotiation")

        # Check if product is negotiable
        if not product.available_inventory != 0:
            errors.append("This product is out of stock and cannot be negotiated")

        if not product.status == "active":
            errors.append("This product is not available for negotiation")

        # Check if buyer is not the seller
        if buyer == product.seller:
            errors.append("You cannot negotiate price for your own product")

        # Check if product is available
        if product.status != "active":
            errors.append("Product is not available for negotiation")

        # Check negotiation deadline
        if (
            product.negotiation_deadline
            and timezone.now() > product.negotiation_deadline
        ):
            errors.append("Negotiation period has expired")

        # Check if buyer has reached max concurrent negotiations
        active_negotiations = PriceNegotiation.objects.filter(
            buyer=buyer, status__in=["pending", "countered"]
        ).count()

        max_concurrent = getattr(settings, "MAX_CONCURRENT_NEGOTIATIONS", 5)
        if active_negotiations >= max_concurrent:
            errors.append(f"Maximum concurrent negotiations ({max_concurrent}) reached")

        duration = (timezone.now() - start_time).total_seconds() * 1000
        logger.info(f"Negotiation eligibility validation completed in {duration:.2f}ms")

        return {"is_valid": len(errors) == 0, "errors": errors}

    @staticmethod
    def validate_offer_price(
        product: Product, offered_price: Decimal, buyer: User
    ) -> Dict[str, any]:
        """Validate the offered price against business rules"""
        start_time = timezone.now()

        errors = []

        # Basic validation
        if offered_price <= 0:
            errors.append("Offered price must be greater than zero")

        # Check minimum acceptable price
        if (
            product.minimum_acceptable_price
            and offered_price < product.minimum_acceptable_price
        ):
            errors.append(
                f"Offered price is below minimum acceptable price of ${product.minimum_acceptable_price}"
            )

        # Check if offer is reasonable (e.g., at least 30% of original price)
        min_reasonable = product.price * Decimal("0.3")
        if offered_price < min_reasonable:
            errors.append(
                f"Offered price is too low. Minimum reasonable offer is ${min_reasonable}"
            )

        # Check if offer is higher than original price
        if offered_price > product.price:
            errors.append("Offered price cannot be higher than the original price")

        # Check buyer's recent negotiation behavior (anti-spam)
        recent_negotiations = PriceNegotiation.objects.filter(
            buyer=buyer, created_at__gte=timezone.now() - timezone.timedelta(hours=1)
        ).count()

        if recent_negotiations >= 10:  # Configurable limit
            errors.append(
                "Too many negotiations in the last hour. Please try again later"
            )

        duration = (timezone.now() - start_time).total_seconds() * 1000
        logger.info(f"Offer price validation completed in {duration:.2f}ms")

        return {"is_valid": len(errors) == 0, "errors": errors}


class NegotiationService:
    """Core negotiation business logic service"""

    @staticmethod
    def initiate_negotiation(
        product: Product,
        buyer: User,
        offered_price: Decimal,
        notes: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, any]]:
        """Initiate a new negotiation"""
        start_time = timezone.now()

        # Validate eligibility
        eligibility = NegotiationValidationService.validate_negotiation_eligibility(
            product, buyer
        )
        if not eligibility["is_valid"]:
            return False, {"errors": eligibility["errors"]}

        # Validate offer price
        price_validation = NegotiationValidationService.validate_offer_price(
            product, offered_price, buyer
        )
        if not price_validation["is_valid"]:
            return False, {"errors": price_validation["errors"]}
        existing_negotiation = PriceNegotiation.objects.filter(
            product=product, buyer=buyer, status__in=["pending", "countered"]
        ).first()
        if existing_negotiation:
            return False, {
                "errors": [
                    "You already have an active negotiation for this product. Please wait for counter offer."
                ]
            }
        try:
            with transaction.atomic():
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
                        buyer=buyer,
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
                    user=buyer,
                    price=offered_price,
                    notes=notes or f"Buyer offered ${offered_price} for the product",
                )

                # Invalidate cache
                CacheManager.invalidate(
                    "negotiation", product_id=product.id, buyer_id=buyer.id
                )

                duration = (timezone.now() - start_time).total_seconds() * 1000
                logger.info(f"Negotiation initiated in {duration:.2f}ms")

                return True, {
                    "negotiation": negotiation,
                    "created": created,
                    "message": "Negotiation initiated successfully",
                }

        except Exception as e:
            logger.error(f"Error initiating negotiation: {str(e)}")
            return False, {"errors": [f"Failed to initiate negotiation: {str(e)}"]}

    @staticmethod
    def respond_to_negotiation(
        negotiation: PriceNegotiation,
        user: User,
        response_type: str,
        counter_price: Optional[Decimal] = None,
        notes: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, any]]:
        """Unified method to handle negotiation responses from both buyers and sellers"""
        start_time = timezone.now()

        # Validate response type
        if response_type not in ["accept", "reject", "counter"]:
            return False, {"errors": ["Invalid response type"]}

        # Determine user role and validate permissions
        is_seller = user == negotiation.seller
        is_buyer = user == negotiation.buyer

        if not (is_seller or is_buyer):
            return False, {
                "errors": ["You are not authorized to respond to this negotiation"]
            }

        # Validate negotiation status based on user role
        if is_seller and negotiation.status not in ["pending", "countered"]:
            return False, {
                "errors": [
                    f"Seller cannot respond to negotiation with status: {negotiation.status}"
                ]
            }

        if is_buyer and negotiation.status != "countered":
            return False, {"errors": ["Buyer can only respond to counter offers"]}

        # Check round limits
        max_rounds = negotiation.product.max_negotiation_rounds or 5
        if negotiation.history.count() >= max_rounds:
            return False, {"errors": ["Maximum negotiation rounds reached"]}

        try:
            with transaction.atomic():
                previous_offer = negotiation.offered_price
                user_role = "seller" if is_seller else "buyer"

                if response_type == "accept":
                    negotiation.status = "accepted"
                    negotiation.final_price = negotiation.offered_price
                    negotiation.save()

                    # Record in history
                    NegotiationHistory.objects.create(
                        negotiation=negotiation,
                        action="price_accepted",
                        user=user,
                        price=negotiation.offered_price,
                        notes=notes
                        or f"{user_role.title()} accepted the offer of ${negotiation.offered_price}",
                    )

                    message = "Offer accepted successfully"

                elif response_type == "reject":
                    negotiation.status = "rejected"
                    negotiation.save()

                    # Record in history
                    NegotiationHistory.objects.create(
                        negotiation=negotiation,
                        action="price_rejected",
                        user=user,
                        price=negotiation.offered_price,
                        notes=notes
                        or f"{user_role.title()} rejected the offer of ${negotiation.offered_price}",
                    )

                    message = "Offer rejected successfully"

                elif response_type == "counter":
                    if not counter_price:
                        return False, {"errors": ["Counter price is required"]}

                    # Validate counter price based on user role
                    validation_result = NegotiationService._validate_counter_price(
                        counter_price, negotiation, is_seller
                    )
                    if not validation_result[0]:
                        return False, {"errors": validation_result[1]}

                    negotiation.status = "countered"
                    negotiation.offered_price = counter_price
                    negotiation.save()

                    # Record in history
                    NegotiationHistory.objects.create(
                        negotiation=negotiation,
                        action="price_countered",
                        user=user,
                        price=counter_price,
                        notes=notes
                        or f"{user_role.title()} counter-offered ${counter_price} (previous: ${previous_offer})",
                    )

                    message = (
                        f"Counter offer of ${counter_price} submitted successfully"
                    )

                # Invalidate cache
                CacheManager.invalidate("negotiation", id=negotiation.id)
                CacheManager.invalidate("product", id=negotiation.product.id)

                # Send appropriate notifications
                if is_seller:
                    NegotiationNotificationService.notify_buyer_response(
                        negotiation, response_type
                    )
                else:
                    NegotiationNotificationService.notify_seller_response(
                        negotiation, response_type
                    )

                duration = (timezone.now() - start_time).total_seconds() * 1000
                logger.info(
                    f"Negotiation response processed in {duration:.2f}ms by {user_role}"
                )

                return True, {
                    "negotiation": negotiation,
                    "message": message,
                    "previous_offer": previous_offer,
                }

        except Exception as e:
            logger.error(f"Error responding to negotiation: {str(e)}")
            return False, {"errors": [f"Failed to process response: {str(e)}"]}

    @staticmethod
    def _validate_counter_price(
        counter_price: Decimal, negotiation: PriceNegotiation, is_seller: bool
    ) -> Tuple[bool, List[str]]:
        """Validate counter price based on user role"""
        if counter_price <= 0:
            return False, ["Counter price must be greater than zero"]

        if is_seller:
            # Seller's counter should be higher than buyer's offer
            if counter_price <= negotiation.offered_price:
                return False, ["Counter price should be higher than the current offer"]

            if counter_price > negotiation.original_price:
                return False, ["Counter price cannot exceed original price"]
        else:
            # Buyer's counter should be lower than seller's counter but reasonable
            if counter_price >= negotiation.offered_price:
                return False, ["Counter price should be lower than the current offer"]

            # Optional: Add minimum price validation for buyers
            min_acceptable = negotiation.original_price * Decimal(
                "0.1"
            )  # 10% of original
            if counter_price < min_acceptable:
                return False, ["Counter price is too low"]

        return True, []


class NegotiationAnalyticsService:
    """Service for negotiation analytics and insights"""

    @staticmethod
    def get_negotiation_stats(product: Product) -> Dict[str, any]:
        """Get negotiation statistics for a product"""
        cache_key = CacheKeyManager.make_key(
            "negotiation", "stats", product_id=product.id
        )

        try:
            from django.core.cache import cache

            cached_stats = cache.get(cache_key)
            if cached_stats:
                return cached_stats
        except Exception:
            pass

        start_time = timezone.now()

        negotiations = PriceNegotiation.objects.filter(product=product)

        stats = {
            "total_negotiations": negotiations.count(),
            "accepted_negotiations": negotiations.filter(status="accepted").count(),
            "rejected_negotiations": negotiations.filter(status="rejected").count(),
            "pending_negotiations": negotiations.filter(
                status__in=["pending", "countered"]
            ).count(),
            "average_offered_price": 0,
            "average_final_price": 0,
            "success_rate": 0,
        }

        if stats["total_negotiations"] > 0:
            # Calculate averages
            offered_prices = [float(n.offered_price) for n in negotiations]
            stats["average_offered_price"] = sum(offered_prices) / len(offered_prices)

            accepted_negotiations = negotiations.filter(
                status="accepted", final_price__isnull=False
            )
            if accepted_negotiations.exists():
                final_prices = [float(n.final_price) for n in accepted_negotiations]
                stats["average_final_price"] = sum(final_prices) / len(final_prices)

            # Calculate success rate
            stats["success_rate"] = (
                stats["accepted_negotiations"] / stats["total_negotiations"]
            ) * 100

        # Cache for 1 hour
        try:
            from django.core.cache import cache

            cache.set(cache_key, stats, 3600)
        except Exception:
            pass

        duration = (timezone.now() - start_time).total_seconds() * 1000
        logger.info(f"Negotiation stats calculated in {duration:.2f}ms")

        return stats

    @staticmethod
    def get_user_negotiation_history(
        user: User, limit: int = 20
    ) -> List[Dict[str, any]]:
        """Get user's negotiation history with caching"""
        cache_key = CacheKeyManager.make_key(
            "negotiation", "user_history", user_id=user.id, limit=limit
        )

        try:
            from django.core.cache import cache

            cached_history = cache.get(cache_key)
            if cached_history:
                return cached_history
        except Exception:
            pass

        start_time = timezone.now()

        # Get negotiations where user is buyer or seller
        negotiations = (
            PriceNegotiation.objects.filter(
                models.Q(buyer=user) | models.Q(seller=user)
            )
            .select_related("product", "buyer", "seller")
            .order_by("-created_at")[:limit]
        )

        history = []
        for negotiation in negotiations:
            history.append(
                {
                    "id": negotiation.id,
                    "product_name": negotiation.product.title,
                    "original_price": float(negotiation.original_price),
                    "offered_price": float(negotiation.offered_price),
                    "final_price": (
                        float(negotiation.final_price)
                        if negotiation.final_price
                        else None
                    ),
                    "status": negotiation.status,
                    "role": "buyer" if negotiation.buyer == user else "seller",
                    "created_at": negotiation.created_at,
                    "updated_at": negotiation.updated_at,
                }
            )

        # Cache for 30 minutes
        try:
            from django.core.cache import cache

            cache.set(cache_key, history, 1800)
        except Exception:
            pass

        duration = (timezone.now() - start_time).total_seconds() * 1000
        logger.info(f"User negotiation history fetched in {duration:.2f}ms")

        return history


class NegotiationNotificationService:
    """Service for handling negotiation notifications"""

    @staticmethod
    def notify_seller_response(
        negotiation: PriceNegotiation, response_type: str = None
    ):
        """Notify seller about new offer"""
        # Implementation depends on your notification system
        # This could send email, push notification, or in-app notification
        pass

    @staticmethod
    def notify_buyer_response(negotiation: PriceNegotiation, response_type: str):
        """Notify buyer about seller's response"""
        # Implementation depends on your notification system
        pass

    @staticmethod
    def notify_negotiation_expired(negotiation: PriceNegotiation):
        """Notify parties about expired negotiation"""
        # Implementation depends on your notification system
        pass
