# apps/notifications/services.py
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from apps.transactions.models import TransactionHistory


class EscrowNotificationService:
    """
    Service for sending notifications related to escrow transactions
    """

    @staticmethod
    def send_status_change_notification(
        transaction, old_status, new_status, is_automatic=False
    ):
        """
        Send notifications to relevant parties when transaction status changes

        Args:
            transaction: The escrow transaction that changed
            old_status: Previous status
            new_status: New status
            is_automatic: Whether this was an automatic transition
        """
        # Determine which parties need notification
        notify_buyer = True
        notify_seller = True

        # Create context for notification templates
        context = {
            "transaction": transaction,
            "old_status": old_status,
            "new_status": new_status,
            "is_automatic": is_automatic,
            "timestamp": timezone.now(),
            "frontend_url": settings.FRONTEND_URL,
            "transaction_detail_url": f"{settings.FRONTEND_URL}/transactions/{transaction.tracking_id}",
            "support_email": settings.SUPPORT_EMAIL,
            "company_name": settings.COMPANY_NAME,
        }

        # Send buyer notification
        if notify_buyer:
            EscrowNotificationService._send_buyer_notification(transaction, context)

        # Send seller notification
        if notify_seller:
            EscrowNotificationService._send_seller_notification(transaction, context)

        # Log the notification in history
        notification_type = "automatic" if is_automatic else "manual"
        TransactionHistory.objects.create(
            transaction=transaction,
            status=new_status,
            notes=f"Status change notification ({notification_type}) sent to buyer and seller",
        )

    @staticmethod
    def send_upcoming_auto_transition_reminder(transaction):
        """
        Send a reminder about an upcoming automatic transition

        Args:
            transaction: The escrow transaction with pending auto-transition
        """
        if (
            not transaction.is_auto_transition_scheduled
            or not transaction.next_auto_transition_at
        ):
            return

        # Create context for notification templates
        context = {
            "transaction": transaction,
            "current_status": transaction.status,
            "next_status": transaction.auto_transition_type,
            "transition_time": transaction.next_auto_transition_at,
            "time_remaining": transaction.time_until_auto_transition,
            "frontend_url": settings.FRONTEND_URL,
            "transaction_detail_url": f"{settings.FRONTEND_URL}/transactions/{transaction.tracking_id}",
            "support_email": settings.SUPPORT_EMAIL,
            "company_name": settings.COMPANY_NAME,
        }

        # Determine who to notify based on status
        if transaction.status == "delivered":
            # Notify buyer that transaction will auto-move to inspection
            EscrowNotificationService._send_buyer_reminder(transaction, context)

        elif transaction.status == "inspection":
            # Notify both buyer and seller that transaction will auto-complete
            EscrowNotificationService._send_buyer_reminder(transaction, context)
            EscrowNotificationService._send_seller_reminder(transaction, context)

        elif transaction.status == "disputed":
            # Notify both about pending auto-refund
            EscrowNotificationService._send_buyer_reminder(transaction, context)
            EscrowNotificationService._send_seller_reminder(transaction, context)

    @staticmethod
    def _send_buyer_notification(transaction, context):
        """Helper method to send notification to buyer"""
        if not transaction.buyer or not transaction.buyer.email:
            return

        subject = f"Your escrow transaction {transaction.tracking_id} has been updated"

        # Render email content from template
        html_content = render_to_string(
            "notifications/buyer_status_change.html", context
        )
        text_content = render_to_string(
            "notifications/buyer_status_change.txt", context
        )

        # Send the email
        send_mail(
            subject=subject,
            message=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[transaction.buyer.email],
            html_message=html_content,
            fail_silently=False,
        )

    @staticmethod
    def _send_seller_notification(transaction, context):
        """Helper method to send notification to seller"""
        if not transaction.seller or not transaction.seller.email:
            return

        subject = f"Your escrow transaction {transaction.tracking_id} has been updated"

        # Render email content from template
        html_content = render_to_string(
            "notifications/seller_status_change.html", context
        )
        text_content = render_to_string(
            "notifications/seller_status_change.txt", context
        )

        # Send the email
        send_mail(
            subject=subject,
            message=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[transaction.seller.email],
            html_message=html_content,
            fail_silently=False,
        )

    @staticmethod
    def _send_buyer_reminder(transaction, context):
        """Helper method to send reminder to buyer about upcoming auto-transition"""
        if not transaction.buyer or not transaction.buyer.email:
            return

        subject = f"Action required: Your escrow transaction {transaction.tracking_id} will update soon"

        # Render email content from template
        html_content = render_to_string(
            "notifications/buyer_auto_transition_reminder.html", context
        )
        text_content = render_to_string(
            "notifications/buyer_auto_transition_reminder.txt", context
        )

        # Send the email
        send_mail(
            subject=subject,
            message=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[transaction.buyer.email],
            html_message=html_content,
            fail_silently=False,
        )

    @staticmethod
    def _send_seller_reminder(transaction, context):
        """Helper method to send reminder to seller about upcoming auto-transition"""
        if not transaction.seller or not transaction.seller.email:
            return

        subject = f"Status update: Your escrow transaction {transaction.tracking_id} will update soon"

        # Render email content from template
        html_content = render_to_string(
            "notifications/seller_auto_transition_reminder.html", context
        )
        text_content = render_to_string(
            "notifications/seller_auto_transition_reminder.txt", context
        )

        # Send the email
        send_mail(
            subject=subject,
            message=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[transaction.seller.email],
            html_message=html_content,
            fail_silently=False,
        )
