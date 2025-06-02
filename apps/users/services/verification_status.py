"""
this services is going to check if user was verified his email, phone and identity on profile.
we can be able to update the verification_status field on our custom user with appropriate verification step.
like if all field in profile was verified we change this
verification_status = models.CharField(
    max_length=10,
    choices=VerificationStatus.choices,
    default=VerificationStatus.VERIFIED,
    else
verification_status = models.CharField(
    max_length=10,
    choices=VerificationStatus.choices,
    default=VerificationStatus.UNVERIFIED Or PENDING,
) with the current step user was
)

this a property "verified_status" on profile model we can use to know which one is verified
at the moments, either email, phone or identity.

"""
