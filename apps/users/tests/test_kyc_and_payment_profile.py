import pytest
from django.contrib.auth import get_user_model
from apps.users.models import SellerPaymentProfile
from apps.users.services.kyc_service import KYCService, MockKYCProvider

User = get_user_model()


@pytest.mark.django_db
class TestKYCAndPaymentProfile:

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.user = User.objects.create_user(
            email="seller@example.com",
            password="testpassword123",
            first_name="Seller",
            last_name="Test"
        )
        self.profile = SellerPaymentProfile.objects.create(
            user=self.user,
            bank_name="Access Bank",
            bank_code="044",
            account_number="1234567890",
            account_name="Seller Test",
        )

    def test_payment_profile_creation(self):
        assert self.profile.bank_name == "Access Bank"
        assert self.profile.account_number == "1234567890"
        assert self.profile.kyc_status == SellerPaymentProfile.KYC_STATUS_UNVERIFIED
        assert not self.profile.bvn_verified
        assert not self.profile.nin_verified

    def test_mock_kyc_bvn_verification_success(self):
        # Valid test BVN is '12345678901' in MockKYCProvider
        success = KYCService.verify_bvn(self.profile, "12345678901")
        assert success
        self.profile.refresh_from_db()
        assert self.profile.bvn_verified
        assert self.profile.kyc_status == SellerPaymentProfile.KYC_STATUS_PENDING

    def test_mock_kyc_bvn_verification_failure(self):
        success = KYCService.verify_bvn(self.profile, "wrong-bvn")
        assert not success
        self.profile.refresh_from_db()
        assert not self.profile.bvn_verified
        assert self.profile.kyc_status == SellerPaymentProfile.KYC_STATUS_FAILED

    def test_mock_kyc_nin_verification_success(self):
        # Valid test NIN is '12345678901'
        success = KYCService.verify_nin(self.profile, "12345678901")
        assert success
        self.profile.refresh_from_db()
        assert self.profile.nin_verified

    def test_mock_kyc_full_verification(self):
        # Verify both BVN and NIN to reach fully VERIFIED status
        KYCService.verify_bvn(self.profile, "12345678901")
        KYCService.verify_nin(self.profile, "12345678901")
        self.profile.refresh_from_db()
        assert self.profile.bvn_verified
        assert self.profile.nin_verified
        assert self.profile.kyc_status == SellerPaymentProfile.KYC_STATUS_VERIFIED
