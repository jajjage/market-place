from django.urls import path
from apps.paystack.views import (
    InitializePaymentView,
    ResolveAccountView,
    RegisterSellerPaymentProfileView,
    PaystackWebhookView,
)

app_name = "paystack"

urlpatterns = [
    path("initialize-payment/", InitializePaymentView.as_view(), name="initialize-payment"),
    path("resolve-account/", ResolveAccountView.as_view(), name="resolve-account"),
    path("register-seller/", RegisterSellerPaymentProfileView.as_view(), name="register-seller"),
    path("webhook/", PaystackWebhookView.as_view(), name="webhook"),
]
