import logging

from rest_framework import status
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from django.utils import timezone

from apps.core.permissions import IsOwnerOrReadOnly
from apps.core.views import BaseViewSet
from apps.products.product_inventory.services import InventoryService
from apps.products.product_negotiation.models import (
    PriceNegotiation,
    NegotiationHistory,
)


class ProductNegotiationViewSet(BaseViewSet):
    permission_classes = [IsOwnerOrReadOnly]
    logger = logging.getLogger(__name__)

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
