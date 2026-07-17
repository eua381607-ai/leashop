import json
import logging

import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


from orders.models import Order

from .services import fulfill_order, process_fedapay_event, process_mobile_money_callback

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def stripe_webhook_view(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        logger.warning("Stripe webhook signature/payload invalid: %s", exc)
        return HttpResponse(status=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("metadata", {}).get("order_id")
        payment_intent_id = session.get("payment_intent", "")

        if order_id:
            try:
                order = Order.objects.get(pk=order_id)
            except Order.DoesNotExist:
                logger.error("Stripe webhook: order %s not found", order_id)
                return HttpResponse(status=200)
            fulfill_order(order, payment_intent_id=payment_intent_id)

    return HttpResponse(status=200)


@csrf_exempt
@require_POST
def mobile_money_callback(request):
    signature = request.META.get("HTTP_X_MOBILE_MONEY_SIGNATURE", "")
    if settings.MOBILE_MONEY_WEBHOOK_SECRET and signature != settings.MOBILE_MONEY_WEBHOOK_SECRET:
        logger.warning("Mobile money callback invalid signature")
        return HttpResponse(status=403)

    try:
        payload = json.loads(request.body)
    except ValueError:
        logger.warning("Mobile money callback invalid JSON")
        return HttpResponse(status=400)

    transaction_id = payload.get("transaction_id") or payload.get("id")
    order_id = payload.get("order_id")
    status = payload.get("status")

    if not order_id or not transaction_id or not status:
        logger.warning("Mobile money callback missing required fields")
        return HttpResponse(status=400)

    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        logger.warning("Mobile money callback order not found: %s", order_id)
        return HttpResponse(status=404)

    processed = process_mobile_money_callback(order, transaction_id=transaction_id, status=status)
    return HttpResponse(status=200 if processed else 202)


@csrf_exempt
@require_POST
def fedapay_webhook_view(request):
    try:
        event = json.loads(request.body)
    except ValueError:
        logger.warning("FedaPay webhook invalid JSON")
        return HttpResponse(status=400)

    try:
        processed = process_fedapay_event(event)
    except Exception as exc:
        logger.exception("FedaPay webhook processing failed: %s", exc)
        return HttpResponse(status=500)

    return HttpResponse(status=200 if processed else 202)
