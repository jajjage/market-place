from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from .models import InventoryTransaction


@shared_task
def send_low_inventory_alert(product_id, current_available):
    """
    Send alert when inventory is low
    """
    from apps.products.models import Product

    try:
        product = Product.objects.get(id=product_id)

        # Define threshold (could be a product field or setting)
        low_inventory_threshold = getattr(settings, "LOW_INVENTORY_THRESHOLD", 5)

        if current_available <= low_inventory_threshold:
            subject = f"Low Inventory Alert: {product.title}"
            message = f"""
            Product: {product.title}
            Current Available Inventory: {current_available}
            Total Inventory: {product.total_inventory}
            In Escrow: {product.in_escrow_inventory}
            Please restock this product soon.
            """

            # Send to product seller
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[product.seller.email],
                fail_silently=False,
            )

    except Product.DoesNotExist:
        pass


@shared_task
def generate_inventory_report(user_id, date_from=None, date_to=None):
    """
    Generate inventory report for a user's products
    """
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from datetime import timedelta

    User = get_user_model()

    try:
        user = User.objects.get(id=user_id)

        # Default to last 30 days if no dates provided
        if not date_to:
            date_to = timezone.now()
        if not date_from:
            date_from = date_to - timedelta(days=30)

        # Get user's products
        products = user.products.filter(is_active=True)

        # Get transactions for these products
        transactions = InventoryTransaction.objects.filter(
            product__in=products, created_at__range=[date_from, date_to]
        ).select_related("product")

        # Generate report data
        report_data = {
            "user": user.username,
            "date_range": f"{date_from.date()} to {date_to.date()}",
            "total_transactions": transactions.count(),
            "products_count": products.count(),
            "transactions_by_type": {},
        }

        # Group by transaction type
        for transaction in transactions:
            t_type = transaction.get_transaction_type_display()
            if t_type not in report_data["transactions_by_type"]:
                report_data["transactions_by_type"][t_type] = 0
            report_data["transactions_by_type"][t_type] += 1

        # Here you could save the report, send via email, etc.
        # For now, we'll just return the data
        return report_data

    except User.DoesNotExist:
        return {"error": "User not found"}


@shared_task
def cleanup_old_inventory_transactions(days_old=365):
    """
    Clean up old inventory transactions (optional maintenance task)
    """
    from django.utils import timezone
    from datetime import timedelta

    cutoff_date = timezone.now() - timedelta(days=days_old)

    old_transactions = InventoryTransaction.objects.filter(created_at__lt=cutoff_date)

    count = old_transactions.count()
    old_transactions.delete()

    return f"Deleted {count} inventory transactions older than {days_old} days"
