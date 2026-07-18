from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.core.models import BaseModel


class SellerPaymentProfile(BaseModel):
    """
    Represents a seller's payment and bank information, isolated
    from general profile details.
    """

    KYC_STATUS_UNVERIFIED = "unverified"
    KYC_STATUS_PENDING = "pending"
    KYC_STATUS_VERIFIED = "verified"
    KYC_STATUS_FAILED = "failed"

    KYC_STATUS_CHOICES = [
        (KYC_STATUS_UNVERIFIED, _("Unverified")),
        (KYC_STATUS_PENDING, _("Pending")),
        (KYC_STATUS_VERIFIED, _("Verified")),
        (KYC_STATUS_FAILED, _("Failed")),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_profile",
        help_text=_("The user this payment profile belongs to"),
    )

    # Banking credentials
    bank_name = models.CharField(
        max_length=100,
        help_text=_("Name of the settlement bank"),
    )
    bank_code = models.CharField(
        max_length=10,
        help_text=_("Bank code for transfer routing"),
    )
    account_number = models.CharField(
        max_length=20,
        help_text=_("NUBAN bank account number"),
    )
    account_name = models.CharField(
        max_length=150,
        help_text=_("Verified bank account name"),
    )

    # Paystack payment fields
    paystack_subaccount_code = models.CharField(
        max_length=50,
        blank=True,
        help_text=_("Paystack subaccount code for split payouts"),
    )
    paystack_recipient_code = models.CharField(
        max_length=50,
        blank=True,
        help_text=_("Paystack transfer recipient code for direct payouts"),
    )

    # Identity / KYC Verification
    bvn_verified = models.BooleanField(
        default=False,
        help_text=_("Whether the BVN matches the account details"),
    )
    nin_verified = models.BooleanField(
        default=False,
        help_text=_("Whether the National Identity Number is verified"),
    )
    kyc_status = models.CharField(
        max_length=20,
        choices=KYC_STATUS_CHOICES,
        default=KYC_STATUS_UNVERIFIED,
        help_text=_("Current status of KYC/identity verification"),
    )

    class Meta:
        db_table = "seller_payment_profiles"
        verbose_name = _("Seller Payment Profile")
        verbose_name_plural = _("Seller Payment Profiles")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["kyc_status"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.bank_name} ({self.account_number})"
