import logging
import smtplib

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.urls import reverse

from cart.services import resolve_cart

from .models import Order, OrderItem

logger = logging.getLogger(__name__)


def _send_order_reminder_email(order, request):
    if hasattr(request, "build_absolute_uri"):
        order_detail_url = request.build_absolute_uri(reverse("orders:order_detail", args=[order.pk]))
    else:
        order_detail_url = settings.SITE_BASE_URL.rstrip("/") + reverse("orders:order_detail", args=[order.pk])
    subject = f"Votre commande #{order.pk} est bien enregistrée"
    body = (
        f"Bonjour,\n\n"
        f"Votre commande #{order.pk} a bien été enregistrée sur LeaShop. "
        f"Vous pouvez suivre son avancement ici : {order_detail_url}\n\n"
        "Merci de finaliser votre paiement afin de confirmer la commande et recevoir votre facture."
    )
    message = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, [order.email])
    try:
        message.send(fail_silently=False)
    except (OSError, smtplib.SMTPException) as exc:
        logger.warning("Order reminder email could not be sent for order %s: %s", order.pk, exc)


@transaction.atomic
def create_order_from_cart(request, address, email, payment_method="card", mobile_money_phone=""):
    """Snapshots the current cart into a new pending Order + OrderItems.
    Does not touch stock yet — stock is decremented only once payment
    confirms (see payments.services.fulfill_order)."""
    cart = resolve_cart(request.cart)
    items = list(cart.items.select_related("variant__product"))

    if not items:
        raise ValueError("Le panier est vide.")

    subtotal = sum((item.line_total for item in items), start=0)

    order = Order.objects.create(
        user=request.user if request.user.is_authenticated else None,
        email=email,
        shipping_full_name=address.full_name,
        shipping_phone_number=address.phone_number,
        shipping_address_line1=address.address_line1,
        shipping_address_line2=address.address_line2,
        shipping_city=address.city,
        shipping_state=address.state,
        shipping_postal_code=address.postal_code,
        shipping_country=address.country,
        subtotal_amount=subtotal,
        total_amount=subtotal,  # extend here for shipping/tax if needed
        payment_method=payment_method,
        mobile_money_phone=mobile_money_phone or address.phone_number,
    )

    for item in items:
        OrderItem.objects.create(
            order=order,
            variant=item.variant,
            product_name=item.variant.product.name,
            variant_label=item.variant.label,
            sku=item.variant.full_sku,
            unit_price=item.variant.price,
            quantity=item.quantity,
        )

    cart.items.all().delete()
    transaction.on_commit(lambda: _send_order_reminder_email(order, request))

    return order
