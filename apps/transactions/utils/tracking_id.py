import hashlib
from django.utils import timezone
import uuid


def generate_tracking_id(variant, buyer, seller):
    """
    Generate a unique tracking ID for escrow transactions

    Format: TRK-{first 8 chars of UUID}-{timestamp}-{hash}

    Args:
        variant: The variant being escrowed
        buyer: The buyer user
        seller: The seller user

    Returns:
        A unique tracking ID string
    """
    # Generate base components
    unique_id = str(uuid.uuid4())[:8].upper()
    timestamp = str(int(timezone.now().timestamp()))[-6:]

    # Create a hash of the variant, buyer, and seller IDs
    hash_input = f"{variant.id}-{buyer.id}-{seller.id}-{timestamp}"
    hash_value = hashlib.md5(hash_input.encode()).hexdigest()[:6].upper()

    # Combine into tracking ID format
    tracking_id = f"TRK-{unique_id}-{timestamp}-{hash_value}"

    return tracking_id
