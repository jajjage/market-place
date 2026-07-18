import logging
from abc import ABC, abstractmethod
from django.conf import settings
from apps.users.models import SellerPaymentProfile

logger = logging.getLogger(__name__)


class BaseKYCProvider(ABC):
    """
    Abstract Base Class for identity verification (KYC) providers.
    """

    @abstractmethod
    def verify_bvn(self, payment_profile: SellerPaymentProfile, bvn: str) -> bool:
        """
        Verify the BVN of a seller against their bank details.
        """
        pass

    @abstractmethod
    def verify_nin(self, payment_profile: SellerPaymentProfile, nin: str) -> bool:
        """
        Verify the National Identity Number (NIN) of a seller.
        """
        pass


class MockKYCProvider(BaseKYCProvider):
    """
    A Mock KYC Provider for testing and local development.
    Validates BVN/NIN with preset valid test values.
    """

    VALID_MOCK_BVN = "12345678901"
    VALID_MOCK_NIN = "12345678901"

    def verify_bvn(self, payment_profile: SellerPaymentProfile, bvn: str) -> bool:
        logger.info(f"Mock-verifying BVN for payment profile {payment_profile.id}")
        if bvn == self.VALID_MOCK_BVN:
            payment_profile.bvn_verified = True
            payment_profile.kyc_status = (
                SellerPaymentProfile.KYC_STATUS_VERIFIED
                if payment_profile.nin_verified
                else SellerPaymentProfile.KYC_STATUS_PENDING
            )
            payment_profile.save()
            return True
        else:
            payment_profile.bvn_verified = False
            payment_profile.kyc_status = SellerPaymentProfile.KYC_STATUS_FAILED
            payment_profile.save()
            return False

    def verify_nin(self, payment_profile: SellerPaymentProfile, nin: str) -> bool:
        logger.info(f"Mock-verifying NIN for payment profile {payment_profile.id}")
        if nin == self.VALID_MOCK_NIN:
            payment_profile.nin_verified = True
            payment_profile.kyc_status = (
                SellerPaymentProfile.KYC_STATUS_VERIFIED
                if payment_profile.bvn_verified
                else SellerPaymentProfile.KYC_STATUS_PENDING
            )
            payment_profile.save()
            return True
        else:
            payment_profile.nin_verified = False
            payment_profile.kyc_status = SellerPaymentProfile.KYC_STATUS_FAILED
            payment_profile.save()
            return False


class PaystackKYCProvider(BaseKYCProvider):
    """
    A live KYC Provider that integrates with Paystack's Identity Verification API.
    """

    def verify_bvn(self, payment_profile: SellerPaymentProfile, bvn: str) -> bool:
        logger.info(f"Paystack verification for BVN initiated for user {payment_profile.user.id}")
        # In a real Paystack flow, BVN matches require verifying account details.
        # This will be completed once PaystackClient is fully wired in.
        # For now, it delegates to mock if keys are mock or returns False.
        if settings.PAYSTACK_SECRET_KEY.startswith("sk_test_mock"):
            return MockKYCProvider().verify_bvn(payment_profile, bvn)
        
        # Real Paystack API logic would go here.
        # For the scope of this implementation, we will log and raise/return False unless integrated.
        raise NotImplementedError("Live Paystack KYC validation requires production credentials.")

    def verify_nin(self, payment_profile: SellerPaymentProfile, nin: str) -> bool:
        logger.info(f"Paystack verification for NIN initiated for user {payment_profile.user.id}")
        if settings.PAYSTACK_SECRET_KEY.startswith("sk_test_mock"):
            return MockKYCProvider().verify_nin(payment_profile, nin)
        
        raise NotImplementedError("Live Paystack KYC validation requires production credentials.")


class KYCService:
    """
    Manager service that routes KYC verification requests to the active provider.
    """

    _provider_instance = None

    @classmethod
    def get_provider(cls) -> BaseKYCProvider:
        if cls._provider_instance is None:
            provider_type = getattr(settings, "KYC_PROVIDER", "mock").lower()
            if provider_type == "paystack":
                cls._provider_instance = PaystackKYCProvider()
            else:
                cls._provider_instance = MockKYCProvider()
        return cls._provider_instance

    @classmethod
    def verify_bvn(cls, payment_profile: SellerPaymentProfile, bvn: str) -> bool:
        return cls.get_provider().verify_bvn(payment_profile, bvn)

    @classmethod
    def verify_nin(cls, payment_profile: SellerPaymentProfile, nin: str) -> bool:
        return cls.get_provider().verify_nin(payment_profile, nin)
