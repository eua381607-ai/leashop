from io import BytesIO
import json
import logging
import smtplib

import requests
import stripe
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.db import transaction
from django.urls import reverse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


FEDAPAY_API_BASE_URLS = {
    "sandbox": "https://sandbox-api.fedapay.com/v1",
    "live": "https://api.fedapay.com/v1",
}


def _fedapay_base_url():
    environment = settings.FEDAPAY_ENVIRONMENT.lower()
    return FEDAPAY_API_BASE_URLS.get(environment, FEDAPAY_API_BASE_URLS["sandbox"])


def _fedapay_headers():
    if not settings.FEDAPAY_SECRET_KEY:
        raise ValueError("FEDAPAY_SECRET_KEY is not configured.")

    return {
        "Authorization": f"Bearer {settings.FEDAPAY_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def create_checkout_session(request, order):
    """Creates a Stripe Checkout Session for the given (pending) order and
    returns the URL the customer should be redirected to."""
    line_items = [
        {
            "price_data": {
                "currency": settings.STRIPE_CURRENCY,
                "product_data": {"name": f"{item.product_name} ({item.variant_label})"
                                  if item.variant_label else item.product_name},
                "unit_amount": int(item.unit_price * 100),
            },
            "quantity": item.quantity,
        }
        for item in order.items.all()
    ]

    success_url = request.build_absolute_uri(
        reverse("orders:order_success", args=[order.pk])
    ) + "?session_id={CHECKOUT_SESSION_ID}"
    cancel_url = request.build_absolute_uri(reverse("cart:cart_detail"))

    payment_method_types = list(settings.STRIPE_PAYMENT_METHOD_TYPES)
    session_data = {
        "mode": "payment",
        "payment_method_types": payment_method_types,
        "line_items": line_items,
        "customer_email": order.email,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {"order_id": str(order.pk)},
    }

    if "mobile_money" in payment_method_types:
        session_data["payment_method_options"] = {
            "mobile_money": {"phone_number_collection": {"enabled": True}}
        }

    session = stripe.checkout.Session.create(**session_data)

    order.stripe_checkout_session_id = session.id
    order.save(update_fields=["stripe_checkout_session_id", "updated_at"])

    return session.url


def create_fedapay_checkout_url(request, order):
    if order.payment_method != "fedapay":
        return None

    success_url = request.build_absolute_uri(
        reverse("orders:order_success", args=[order.pk])
    )
    customer_name = order.shipping_full_name.strip() or order.email
    name_parts = customer_name.split(" ", 1)
    customer = {
        "firstname": name_parts[0],
        "lastname": name_parts[1] if len(name_parts) > 1 else "",
        "email": order.email,
    }
    payload = {
        "description": f"Paiement commande LeaShop #{order.pk}",
        "amount": int(order.total_amount),
        "currency": {"iso": settings.FEDAPAY_CURRENCY},
        "callback_url": success_url,
        "custom_metadata": {"order_id": str(order.pk)},
        "customer": customer,
    }

    response = requests.post(
        f"{_fedapay_base_url()}/transactions",
        json=payload,
        headers=_fedapay_headers(),
        timeout=30,
    )
    response.raise_for_status()
    transaction_data = response.json()
    transaction_id = str(transaction_data.get("id") or "")

    token_response = requests.post(
        f"{_fedapay_base_url()}/transactions/{transaction_id}/token",
        headers=_fedapay_headers(),
        timeout=30,
    )
    token_response.raise_for_status()
    token_data = token_response.json()

    order.fedapay_transaction_id = transaction_id
    order.fedapay_reference = transaction_data.get("reference") or ""
    order.fedapay_payment_url = token_data.get("url") or ""
    order.save(
        update_fields=[
            "fedapay_transaction_id",
            "fedapay_reference",
            "fedapay_payment_url",
            "updated_at",
        ]
    )

    if not order.fedapay_payment_url:
        raise ValueError("FedaPay did not return a payment URL.")

    return order.fedapay_payment_url


def retrieve_fedapay_transaction(transaction_id):
    response = requests.get(
        f"{_fedapay_base_url()}/transactions/{transaction_id}",
        headers=_fedapay_headers(),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def process_fedapay_event(event):
    event_name = event.get("name") or event.get("type") or ""
    event_object = event.get("object") or event.get("data", {}).get("object") or {}

    if event_name not in {"transaction.approved", "transaction.updated"}:
        return False

    transaction_id = str(event_object.get("id") or event_object.get("transaction_id") or "")
    if not transaction_id:
        return False

    transaction_data = retrieve_fedapay_transaction(transaction_id)
    status = str(transaction_data.get("status") or event_object.get("status") or "").lower()
    if status != "approved":
        return False

    metadata = transaction_data.get("custom_metadata") or event_object.get("custom_metadata") or {}
    order_id = metadata.get("order_id")
    if not order_id:
        return False

    from orders.models import Order

    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        logger.warning("FedaPay webhook order not found: %s", order_id)
        return False

    if order.fedapay_transaction_id and order.fedapay_transaction_id != transaction_id:
        logger.warning(
            "FedaPay transaction mismatch for order %s: expected %s, got %s",
            order.pk,
            order.fedapay_transaction_id,
            transaction_id,
        )
        return False

    if not order.fedapay_transaction_id:
        order.fedapay_transaction_id = transaction_id
    order.fedapay_reference = transaction_data.get("reference") or order.fedapay_reference
    order.save(update_fields=["fedapay_transaction_id", "fedapay_reference", "updated_at"])
    fulfill_order(order, payment_intent_id=f"fedapay:{transaction_id}")
    return True


def initiate_mobile_money_payment(order):
    if order.payment_method != "mobile_money":
        return None

    if not settings.MOBILE_MONEY_API_URL and settings.DEBUG:
        return {
            "order_id": str(order.pk),
            "status": "pending",
            "provider": "local",
        }

    if not settings.MOBILE_MONEY_API_URL:
        raise ValueError("MOBILE_MONEY_API_URL is not configured.")

    payload = {
        "order_id": str(order.pk),
        "phone_number": order.mobile_money_phone,
        "amount": int(order.total_amount * 100),
        "currency": settings.STRIPE_CURRENCY,
        "description": f"Paiement Mobile Money commande #{order.pk}",
        "callback_url": settings.SITE_BASE_URL.rstrip("/")
        + reverse("payments:mobile_money_callback"),
    }
    headers = {"Content-Type": "application/json"}
    if settings.MOBILE_MONEY_API_KEY:
        headers["Authorization"] = f"Bearer {settings.MOBILE_MONEY_API_KEY}"

    response = requests.post(
        settings.MOBILE_MONEY_API_URL,
        json=payload,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    transaction_id = data.get("transaction_id") or data.get("id") or ""
    order.mobile_money_transaction_id = transaction_id
    order.save(update_fields=["mobile_money_transaction_id", "updated_at"])

    if _is_successful_mobile_money_status(data.get("status")):
        fulfill_order(order, payment_intent_id=f"mobile_money:{transaction_id}")

    return data


def process_mobile_money_callback(order, transaction_id, status):
    if order.payment_method != "mobile_money":
        return False

    if transaction_id:
        order.mobile_money_transaction_id = transaction_id
        order.save(update_fields=["mobile_money_transaction_id", "updated_at"])

    if _is_successful_mobile_money_status(status) and order.status != order.Status.PAID:
        fulfill_order(order, payment_intent_id=f"mobile_money:{transaction_id}")
        return True

    return False


def _is_successful_mobile_money_status(status):
    return str(status).lower() in {"success", "completed", "paid"}


def _build_invoice_pdf(order):
    """Generates a professional invoice PDF for the given order."""
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import Table, TableStyle

    buffer = BytesIO()
    W, H = letter  # 612 x 792 pts

    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setTitle(f"Facture LEASHOP-{order.pk:06d}")

    # ── Helper ─────────────────────────────────────────────────────────────
    def _hex(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))

    PRIMARY   = _hex("4f46e5")   # indigo
    PRIMARY_L = _hex("eef2ff")   # light indigo
    DARK      = _hex("111827")
    GRAY      = _hex("6b7280")
    LIGHT     = _hex("f9fafb")
    SUCCESS   = _hex("16a34a")
    DANGER    = _hex("dc2626")
    WARNING   = _hex("ca8a04")

    def setrgb(c): pdf.setFillColorRGB(*c)
    def setstroke(c): pdf.setStrokeColorRGB(*c)

    # ── Header band ────────────────────────────────────────────────────────
    pdf.setFillColorRGB(*PRIMARY)
    pdf.rect(0, H - 80, W, 80, fill=1, stroke=0)

    # Logo / brand
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(40, H - 46, "LeaShop")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(40, H - 62, "Votre boutique en ligne de confiance")

    # Invoice number — top-right
    invoice_no = f"FACT-{order.pk:06d}"
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawRightString(W - 40, H - 42, invoice_no)
    pdf.setFont("Helvetica", 9)
    pdf.drawRightString(W - 40, H - 57, f"Date : {order.updated_at:%d/%m/%Y}")

    # Status badge
    if order.status == "paid":
        badge_color = SUCCESS
        badge_text = "PAYÉE ✓"
    elif order.status == "cancelled":
        badge_color = DANGER
        badge_text = "ANNULÉE ✗"
    elif order.status == "shipped":
        badge_color = PRIMARY
        badge_text = "EXPÉDIÉE"
    elif order.status == "delivered":
        badge_color = SUCCESS
        badge_text = "LIVRÉE"
    else:
        badge_color = WARNING
        badge_text = "EN ATTENTE"

    bw, bh = 100, 18
    bx = W - 40 - bw
    by = H - 80
    pdf.setFillColorRGB(*badge_color)
    pdf.roundRect(bx, by + 3, bw, bh, 4, fill=1, stroke=0)
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawCentredString(bx + bw / 2, by + 9, badge_text)

    # ── Vendor / Client two-column ─────────────────────────────────────────
    y_info = H - 100

    # Thin separator line
    pdf.setStrokeColorRGB(*_hex("e5e7eb"))
    pdf.setLineWidth(0.5)
    pdf.line(40, y_info - 5, W - 40, y_info - 5)

    col1_x, col2_x = 40, W / 2 + 10

    # "Vendeur" label
    setrgb(PRIMARY)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(col1_x, y_info - 22, "VENDEUR")
    setrgb(DARK)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(col1_x, y_info - 36, "LeaShop SAS")
    setrgb(GRAY)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(col1_x, y_info - 48, "1 Rue du Commerce, 75001 Paris")
    pdf.drawString(col1_x, y_info - 59, "contact@leashop.fr")
    pdf.drawString(col1_x, y_info - 70, "SIRET : 000 000 000 00000")

    # "Client" label
    setrgb(PRIMARY)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(col2_x, y_info - 22, "CLIENT")
    setrgb(DARK)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(col2_x, y_info - 36, order.shipping_full_name or order.email)
    setrgb(GRAY)
    pdf.setFont("Helvetica", 9)
    if order.shipping_address_line1:
        pdf.drawString(col2_x, y_info - 48, order.shipping_address_line1)
        city_line = f"{order.shipping_city or ''} {order.shipping_postal_code or ''}".strip()
        if city_line:
            pdf.drawString(col2_x, y_info - 59, city_line)
        pdf.drawString(col2_x, y_info - 70, order.email)
    else:
        pdf.drawString(col2_x, y_info - 48, order.email)

    # ── Table header ───────────────────────────────────────────────────────
    table_top = y_info - 95
    th = 20  # row height header
    col_widths = [45, 215, 60, 80, 85]  # Ref, Produit, Qté, Prix U., Total
    headers = ["Réf.", "Désignation", "Qté", "Prix unit.", "Total HT"]
    col_x = [40]
    for w in col_widths[:-1]:
        col_x.append(col_x[-1] + w)

    # Header bg
    setrgb(PRIMARY)
    pdf.rect(40, table_top - th, sum(col_widths), th, fill=1, stroke=0)
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 8.5)
    for i, h_text in enumerate(headers):
        x = col_x[i] + 5
        if i >= 2:  # right-align numeric cols
            pdf.drawRightString(col_x[i] + col_widths[i] - 5, table_top - 13, h_text)
        else:
            pdf.drawString(x, table_top - 13, h_text)

    # ── Table rows ─────────────────────────────────────────────────────────
    row_h = 18
    y_row = table_top - th - row_h
    items = list(order.items.all())

    for idx, item in enumerate(items):
        # Alternating row bg
        if idx % 2 == 0:
            setrgb(LIGHT)
            pdf.rect(40, y_row, sum(col_widths), row_h, fill=1, stroke=0)

        setrgb(DARK)
        pdf.setFont("Helvetica", 8.5)
        # Ref
        pdf.drawString(col_x[0] + 5, y_row + 5, f"#{idx + 1:03d}")
        # Designation (truncate)
        designation = item.product_name
        if item.variant_label:
            designation += f" ({item.variant_label})"
        if len(designation) > 42:
            designation = designation[:40] + "…"
        pdf.drawString(col_x[1] + 5, y_row + 5, designation)
        # Qty
        pdf.drawRightString(col_x[2] + col_widths[2] - 5, y_row + 5, str(item.quantity))
        # Unit price
        try:
            price_str = f"{float(item.unit_price):.2f} €"
        except Exception:
            price_str = f"{item.unit_price} €"
        pdf.drawRightString(col_x[3] + col_widths[3] - 5, y_row + 5, price_str)
        # Line total
        try:
            total_str = f"{float(item.line_total):.2f} €"
        except Exception:
            total_str = f"{item.line_total} €"
        pdf.setFont("Helvetica-Bold", 8.5)
        pdf.drawRightString(col_x[4] + col_widths[4] - 5, y_row + 5, total_str)

        y_row -= row_h

    # Bottom border of table
    setstroke(_hex("e5e7eb"))
    pdf.setLineWidth(0.5)
    pdf.line(40, y_row + row_h, 40 + sum(col_widths), y_row + row_h)

    # ── Totals block (right-aligned) ───────────────────────────────────────
    totals_x = col_x[3]
    totals_w = col_widths[3] + col_widths[4]
    y_totals = y_row + row_h - 10

    def draw_total_row(label, amount, bold=False, highlight=False):
        nonlocal y_totals
        y_totals -= 20
        if highlight:
            setrgb(PRIMARY)
            pdf.rect(totals_x, y_totals - 4, totals_w, 18, fill=1, stroke=0)
            pdf.setFillColorRGB(1, 1, 1)
        else:
            setrgb(GRAY if not bold else DARK)

        pdf.setFont("Helvetica-Bold" if bold else "Helvetica", 8.5 if not highlight else 10)
        pdf.drawString(totals_x + 5, y_totals + 2, label)
        try:
            amt_str = f"{float(amount):.2f} €"
        except Exception:
            amt_str = f"{amount} €"
        pdf.drawRightString(totals_x + totals_w - 5, y_totals + 2, amt_str)

    draw_total_row("Sous-total HT", order.total_amount)
    draw_total_row("TVA (0 %)", 0)
    draw_total_row("Livraison", 0)
    draw_total_row("TOTAL TTC", order.total_amount, bold=True, highlight=True)

    # ── Footer ─────────────────────────────────────────────────────────────
    footer_y = 55
    setrgb(PRIMARY)
    pdf.rect(0, 0, W, footer_y - 5, fill=1, stroke=0)
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawCentredString(W / 2, footer_y + 18, "Merci pour votre confiance — LeaShop")
    pdf.setFont("Helvetica", 7)
    pdf.drawCentredString(
        W / 2, footer_y + 6,
        "Ce document est une facture officielle. Conservez-le pour vos archives."
    )
    pdf.drawCentredString(
        W / 2, footer_y - 6,
        f"LeaShop SAS • SIRET 000 000 000 00000 • contact@leashop.fr • leashop.fr"
    )

    # Page number
    setrgb(GRAY)
    pdf.setFont("Helvetica", 7)
    pdf.drawRightString(W - 40, 20, "Page 1 / 1")

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _send_payment_confirmation_email(order):
    invoice_bytes = _build_invoice_pdf(order)
    filename = f"facture-LEASHOP-{order.pk:06d}.pdf"
    order.invoice_file.save(filename, ContentFile(invoice_bytes), save=True)

    invoice_url = settings.SITE_BASE_URL.rstrip("/") + reverse("orders:invoice_download", args=[order.pk])
    subject = f"Facture confirmée — Commande #{order.pk} — LeaShop"
    body = (
        f"Bonjour {order.shipping_full_name or ''},\n\n"
        f"Votre paiement pour la commande #{order.pk} a bien été validé. "
        f"Vous trouverez votre facture (FACT-{order.pk:06d}) en pièce jointe et disponible ici : {invoice_url}\n\n"
        "Merci pour votre confiance et à bientôt sur LeaShop !\n\n"
        "— L'équipe LeaShop"
    )
    message = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, [order.email])
    message.attach(filename, invoice_bytes, "application/pdf")
    try:
        message.send(fail_silently=False)
    except (OSError, smtplib.SMTPException) as exc:
        logger.warning("Payment confirmation email could not be sent for order %s: %s", order.pk, exc)


@transaction.atomic
def fulfill_order(order, payment_intent_id=""):
    """Marks the order as paid and decrements stock for each purchased
    variant. Called from the Stripe webhook once payment is confirmed —
    never trust the client-side redirect alone for this."""
    from orders.models import Order

    if order.status == Order.Status.PAID:
        return  # already processed (webhook can fire more than once)

    order.mark_as_paid(payment_intent_id=payment_intent_id)

    for item in order.items.select_related("variant"):
        if item.variant is not None:
            item.variant.stock_quantity = max(item.variant.stock_quantity - item.quantity, 0)
            item.variant.save(update_fields=["stock_quantity"])

    # Clear the cart that generated this order, if the user still has one.
    if order.user is not None:
        cart = getattr(order.user, "cart", None)
        if cart is not None:
            cart.items.all().delete()

    transaction.on_commit(lambda: _send_payment_confirmation_email(order))
