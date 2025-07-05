# apps/notifications/services/email.py
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings


class EmailNotificationService:
    @staticmethod
    def send_email(subject, template_name, context, recipient_list):
        """
        A utility method to send emails.

        :param subject: Email subject
        :param template_name: Name of the template to use for the email body
        :param context: Dictionary with context data for the template
        :param recipient_list: List of recipient email addresses
        """
        html_message = render_to_string(template_name, context)
        send_mail(
            subject,
            None,  # Plain text message (optional)
            settings.DEFAULT_FROM_EMAIL,
            recipient_list,
            html_message=html_message,
            fail_silently=False,
        )
