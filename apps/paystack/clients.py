import logging
import requests
from django.conf import settings
from decimal import Decimal

logger = logging.getLogger(__name__)


class PaystackClient:
    """
    HTTP client for the Paystack Payment Gateway API.
    Supports mock modes for local testing and development.
    """

    BASE_URL = "https://api.paystack.co"

    def __init__(self):
        self.secret_key = getattr(settings, "PAYSTACK_SECRET_KEY", "")
        self.is_mock = self.secret_key.startswith("sk_test_mock")

        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    def _post(self, path: str, data: dict) -> dict:
        url = f"{self.BASE_URL}{path}"
        try:
            response = requests.post(url, json=data, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Paystack POST request to {path} failed: {str(e)}")
            raise

    def _get(self, path: str, params: dict = None) -> dict:
        url = f"{self.BASE_URL}{path}"
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Paystack GET request to {path} failed: {str(e)}")
            raise

    def initialize_transaction(self, email: str, amount_ngn: Decimal, reference: str, callback_url: str) -> dict:
        """
        Initialize a payment transaction on Paystack.
        Amount is converted to kobo (multiply by 100).
        """
        amount_kobo = int(amount_ngn * 100)

        if self.is_mock:
            logger.info(f"[Mock Paystack] Initializing transaction for {email} - Reference: {reference}")
            return {
                "status": True,
                "message": "Authorization URL created",
                "data": {
                    "authorization_url": f"https://checkout.paystack.com/mock-checkout-{reference}",
                    "access_code": f"mock-access-code-{reference}",
                    "reference": reference
                }
            }

        payload = {
            "email": email,
            "amount": amount_kobo,
            "reference": reference,
            "callback_url": callback_url,
        }
        return self._post("/transaction/initialize", payload)

    def verify_payment(self, reference: str) -> dict:
        """
        Verify transaction payment status.
        """
        if self.is_mock:
            logger.info(f"[Mock Paystack] Verifying payment for reference: {reference}")
            return {
                "status": True,
                "message": "Verification successful",
                "data": {
                    "reference": reference,
                    "status": "success",
                    "amount": 500000,  # 5000 NGN in kobo
                    "gateway_response": "Successful",
                    "customer": {"email": "mock-buyer@example.com"}
                }
            }

        return self._get(f"/transaction/verify/{reference}")

    def resolve_account(self, account_number: str, bank_code: str) -> dict:
        """
        Resolve NUBAN bank account number.
        """
        if self.is_mock:
            logger.info(f"[Mock Paystack] Resolving account: {account_number} with bank code: {bank_code}")
            return {
                "status": True,
                "message": "Account number resolved",
                "data": {
                    "account_number": account_number,
                    "account_name": "JOHN DOE ENTERPRISES"
                }
            }

        params = {"account_number": account_number, "bank_code": bank_code}
        return self._get("/bank/resolve", params=params)

    def create_subaccount(self, business_name: str, settlement_bank: str, account_number: str, percentage_charge: float) -> dict:
        """
        Create subaccount for split transfers.
        """
        if self.is_mock:
            logger.info(f"[Mock Paystack] Creating subaccount for {business_name}")
            return {
                "status": True,
                "message": "Subaccount created successfully",
                "data": {
                    "subaccount_code": f"ACCT_mock_sub_{account_number[-4:]}",
                    "business_name": business_name,
                    "settlement_bank": settlement_bank,
                    "account_number": account_number
                }
            }

        payload = {
            "business_name": business_name,
            "settlement_bank": settlement_bank,
            "account_number": account_number,
            "percentage_charge": percentage_charge,
        }
        return self._post("/subaccount", payload)

    def create_transfer_recipient(self, name: str, account_number: str, bank_code: str) -> dict:
        """
        Create a transfer recipient on Paystack.
        """
        if self.is_mock:
            logger.info(f"[Mock Paystack] Creating transfer recipient: {name} ({account_number})")
            return {
                "status": True,
                "message": "Transfer recipient created successfully",
                "data": {
                    "recipient_code": f"RCP_mock_rec_{account_number[-4:]}",
                    "name": name,
                    "details": {
                        "account_number": account_number,
                        "bank_code": bank_code
                    }
                }
            }

        payload = {
            "type": "nuban",
            "name": name,
            "account_number": account_number,
            "bank_code": bank_code,
            "currency": "NGN"
        }
        return self._post("/transferrecipient", payload)

    def initiate_transfer(self, amount_ngn: Decimal, recipient_code: str, reference: str) -> dict:
        """
        Transfer funds from the platform balance to a seller's bank account.
        """
        amount_kobo = int(amount_ngn * 100)

        if self.is_mock:
            logger.info(f"[Mock Paystack] Transferring {amount_ngn} NGN to recipient {recipient_code}")
            return {
                "status": True,
                "message": "Transfer queued",
                "data": {
                    "reference": reference,
                    "amount": amount_kobo,
                    "recipient": recipient_code,
                    "status": "success",
                    "transfer_code": f"TRF_mock_{reference}"
                }
            }

        payload = {
            "source": "balance",
            "amount": amount_kobo,
            "recipient": recipient_code,
            "reference": reference,
            "reason": f"SafeTrade escrow payout for transaction reference {reference}"
        }
        return self._post("/transfer", payload)
