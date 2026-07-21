from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.checkout_view, name="checkout"),
    path("success/<int:pk>/", views.order_success_view, name="order_success"),
    path("history/", views.order_history_view, name="order_history"),
    path(
        "<int:pk>/confirm-payment/",
        views.confirm_payment_view,
        name="confirm_payment",
    ),
    path("invoice/<int:pk>/", views.invoice_download_view, name="invoice_download"),
    path("<int:pk>/", views.order_detail_view, name="order_detail"),
]
