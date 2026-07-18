import hmac
import hashlib
import json
import logging
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from apps.paystack.clients import PaystackClient
from apps.transactions.models import EscrowTransaction, SellerBalanceLedger
from apps.transactions.services.escrow_services import EscrowTransactionService
from apps.transactions.services.ledger_service import SellerBalanceService
from apps.users.models import SellerPaymentProfile

logger = logging.getLogger(__name__)


class InitializePaymentView(APIView):
    """
    Endpoint for initializing checkout payment for an Escrow transaction.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        transaction_id = request.data.get("transaction_id")
        if not transaction_id:
            return Response(
                {"error": "transaction_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            escrow_transaction = EscrowTransaction.objects.get(
                id=transaction_id, buyer=request.user
            )
        except EscrowTransaction.DoesNotExist:
            return Response(
                {"error": "Escrow transaction not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if escrow_transaction.status != EscrowTransaction.STATUS_INITIATED:
            return Response(
                {"error": f"Cannot initialize payment for transaction in status: {escrow_transaction.status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = PaystackClient()
        callback_url = request.build_absolute_uri("/api/v1/paystack/callback/")

        try:
            res = client.initialize_transaction(
                email=request.user.email,
                amount_ngn=escrow_transaction.total_amount,
                reference=escrow_transaction.tracking_id,
                callback_url=callback_url,
            )
            if res.get("status"):
                return Response(res["data"], status=status.HTTP_200_OK)
            return Response(
                {"error": res.get("message", "Failed to initialize payment")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Error initializing payment: {str(e)}")
            return Response(
                {"error": "Internal server error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ResolveAccountView(APIView):
    """
    Endpoint for resolving bank details.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        account_number = request.query_params.get("account_number")
        bank_code = request.query_params.get("bank_code")

        if not account_number or not bank_code:
            return Response(
                {"error": "account_number and bank_code are required query parameters"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = PaystackClient()
        try:
            res = client.resolve_account(account_number, bank_code)
            if res.get("status"):
                return Response(res["data"], status=status.HTTP_200_OK)
            return Response(
                {"error": res.get("message", "Unable to resolve bank account")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Error resolving bank account: {str(e)}")
            return Response(
                {"error": "Failed to resolve bank account details"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class RegisterSellerPaymentProfileView(APIView):
    """
    Endpoint for registering or updating a seller's payment details.
    Verifies bank account details before creating the payment profile.
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        bank_name = request.data.get("bank_name")
        bank_code = request.data.get("bank_code")
        account_number = request.data.get("account_number")

        if not all([bank_name, bank_code, account_number]):
            return Response(
                {"error": "bank_name, bank_code, and account_number are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = PaystackClient()
        
        # 1. Resolve and verify the bank details
        try:
            resolve_res = client.resolve_account(account_number, bank_code)
            if not resolve_res.get("status"):
                return Response(
                    {"error": f"Failed to verify bank details: {resolve_res.get('message')}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            resolved_account_name = resolve_res["data"]["account_name"]
        except Exception as e:
            logger.error(f"Error during bank details verification: {str(e)}")
            return Response(
                {"error": "Could not verify bank details with Paystack"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Create the transfer recipient on Paystack
        try:
            recipient_res = client.create_transfer_recipient(
                name=resolved_account_name,
                account_number=account_number,
                bank_code=bank_code,
            )
            if not recipient_res.get("status"):
                return Response(
                    {"error": f"Failed to create payout recipient: {recipient_res.get('message')}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            recipient_code = recipient_res["data"]["recipient_code"]
        except Exception as e:
            logger.error(f"Error creating transfer recipient: {str(e)}")
            return Response(
                {"error": "Failed to configure payout routing with gateway"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 3. Save or update the SellerPaymentProfile
        profile, created = SellerPaymentProfile.objects.update_or_create(
            user=request.user,
            defaults={
                "bank_name": bank_name,
                "bank_code": bank_code,
                "account_number": account_number,
                "account_name": resolved_account_name,
                "paystack_recipient_code": recipient_code,
            },
        )

        return Response(
            {
                "message": "Payment profile saved successfully",
                "data": {
                    "id": profile.id,
                    "bank_name": profile.bank_name,
                    "account_number": profile.account_number,
                    "account_name": profile.account_name,
                    "recipient_code": profile.paystack_recipient_code,
                },
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class PaystackWebhookView(APIView):
    """
    Webhook handler for processing asynchronous Paystack event notifications.
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        payload = request.body
        signature = request.headers.get("x-paystack-signature")

        if not signature:
            logger.warning("Paystack webhook missing signature header")
            return HttpResponse(status=401)

        # Verify signature
        webhook_secret = getattr(settings, "PAYSTACK_WEBHOOK_SECRET", "")
        
        # Bypass signature check in mock environment if secret is a mock
        is_mock_env = webhook_secret.startswith("mock_") or getattr(settings, "TESTING", False)
        
        if not is_mock_env:
            hash_val = hmac.new(
                webhook_secret.encode("utf-8"),
                payload,
                hashlib.sha512
            ).hexdigest()

            if hash_val != signature:
                logger.warning("Paystack webhook signature verification failed")
                return HttpResponse(status=401)

        try:
            event_data = json.loads(payload)
            event_type = event_data.get("event")
            data = event_data.get("data", {})
            logger.info(f"Received Paystack Webhook event: {event_type}")

            if event_type == "charge.success":
                reference = data.get("reference")
                self._handle_charge_success(reference)

            elif event_type == "transfer.success":
                reference = data.get("reference")
                self._handle_transfer_success(reference, data)

            elif event_type == "transfer.failed":
                reference = data.get("reference")
                self._handle_transfer_failed(reference, data)

            return HttpResponse(status=200)

        except Exception as e:
            logger.error(f"Error handling Paystack webhook: {str(e)}")
            return HttpResponse(status=500)

    @transaction.atomic
    def _handle_charge_success(self, reference: str):
        """
        Processes successful escrow payments.
        Updates transaction status and locks the funds.
        """
        try:
            escrow_transaction = EscrowTransaction.objects.get(tracking_id=reference)
            if escrow_transaction.status == EscrowTransaction.STATUS_INITIATED:
                # Transition status using system actor (user=None)
                EscrowTransactionService._update_escrow_transaction_status(
                    escrow_transaction=escrow_transaction,
                    new_status=EscrowTransaction.STATUS_PAYMENT_RECEIVED,
                    user=None,
                    notes="Payment confirmed successfully via Paystack webhook.",
                )
                logger.info(f"Escrow transaction {escrow_transaction.id} transitioned to payment_received")
        except EscrowTransaction.DoesNotExist:
            logger.error(f"EscrowTransaction not found for payment reference: {reference}")

    @transaction.atomic
    def _handle_transfer_success(self, reference: str, data: dict):
        """
        Processes successful payout transfers to sellers.
        """
        logger.info(f"Payout transfer successful for reference: {reference}")
        # Custom logging or settlement recording logic can be added here.

    @transaction.atomic
    def _handle_transfer_failed(self, reference: str, data: dict):
        """
        Processes failed payout transfers. Reverts the debit in the ledger.
        """
        logger.error(f"Payout transfer failed for reference: {reference}")
        # In a failure scenario, we record a credit entry to correct the balance.
        # Find the original ledger debit
        try:
            original_debit = SellerBalanceLedger.objects.get(
                entry_type=SellerBalanceLedger.ENTRY_PAYOUT_DEBIT,
                description__contains=reference
            )
            SellerBalanceService.record_entry(
                seller=original_debit.seller,
                amount=abs(original_debit.amount),
                entry_type=SellerBalanceLedger.ENTRY_ADJUSTMENT,
                transaction_obj=original_debit.transaction,
                description=f"Reversal of failed payout transfer reference {reference}",
            )
            logger.info(f"Reverted failed payout debit for seller {original_debit.seller.id}")
        except SellerBalanceLedger.DoesNotExist:
            logger.error(f"Original payout debit ledger entry not found for failed transfer reference: {reference}")
