from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("stripe/webhook/", views.stripe_webhook_view, name="stripe_webhook"),
    path("fedapay/webhook/", views.fedapay_webhook_view, name="fedapay_webhook"),
    path("mobile-money/callback/", views.mobile_money_callback, name="mobile_money_callback"),
]
