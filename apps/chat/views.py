from django.shortcuts import render, redirect

# from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .models import ChatMessage

# from apps.notifications.services.notification_service import NotificationService
from apps.users.models import CustomUser

# from django.http import HttpResponse
from django.conf import settings


def simple_login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        user = CustomUser.objects.filter(email=email).first()
        if user:
            refresh = RefreshToken.for_user(user)
            response = redirect("chat_room")
            response.set_cookie(
                key=settings.JWT_AUTH_COOKIE,
                value=str(refresh.access_token),
                httponly=True,
                samesite=settings.JWT_AUTH_SAMESITE,
                secure=settings.JWT_AUTH_SECURE,
                path=settings.JWT_AUTH_PATH,
            )
            response.set_cookie(
                key=settings.JWT_AUTH_REFRESH_COOKIE,
                value=str(refresh),
                httponly=True,
                samesite=settings.JWT_AUTH_SAMESITE,
                secure=settings.JWT_AUTH_SECURE,
                path=settings.JWT_AUTH_PATH,
            )
            return response
    return render(request, "chat/login.html")


def chat_room(request):
    if not request.user.is_authenticated:
        # This is a simple check. A more robust solution would be a custom decorator
        # that uses the project's JWT authentication backend.
        return redirect("simple_login")

    if request.method == "POST":
        message = request.POST.get("message")
        if message:
            ChatMessage.objects.create(user=request.user, message=message)

            # The notification logic will be moved to the consumer
            return redirect("chat_room")

    messages = ChatMessage.objects.all().order_by("timestamp")
    return render(request, "chat/chat_room.html", {"messages": messages})
