import requests

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.forms import AddressForm
from accounts.models import Address
from payments.services import (
    create_checkout_session,
    create_fedapay_checkout_url,
    fulfill_order,
    initiate_mobile_money_payment,
)

from . import services
from .models import Order


def _checkout_context(cart, addresses, form):
    return {
        "addresses": addresses,
        "new_address_form": form,
        "cart": cart,
        "fedapay_available": bool(settings.FEDAPAY_SECRET_KEY),
        "mobile_money_available": settings.DEBUG or bool(settings.MOBILE_MONEY_API_URL),
    }


def _can_confirm_mobile_money_locally(order):
    return (
        settings.DEBUG
        and order.payment_method == "mobile_money"
        and order.status == Order.Status.PENDING
    )


@login_required
def checkout_view(request):
    cart = request.cart
    if cart.total_quantity == 0:
        messages.warning(request, "Votre panier est vide.")
        return redirect("cart:cart_detail")

    addresses = request.user.addresses.all()

    if request.method == "POST":
        address_id = request.POST.get("address_id")
        form = AddressForm(request.POST)

        if address_id == "new":
            if form.is_valid():
                address = form.save(commit=False)
                address.user = request.user
                address.save()
            else:
                messages.error(request, "Veuillez vérifier les champs de votre nouvelle adresse (certains sont obligatoires).")
                return render(
                    request,
                    "orders/checkout.html",
                    _checkout_context(cart, addresses, form),
                )
        elif address_id:
            address = Address.objects.filter(pk=address_id, user=request.user).first()
            if not address:
                messages.error(request, "Veuillez sélectionner une adresse valide.")
                return render(
                    request,
                    "orders/checkout.html",
                    _checkout_context(cart, addresses, form),
                )
        else:
            return render(
                request,
                "orders/checkout.html",
                _checkout_context(cart, addresses, form),
            )

        payment_method = request.POST.get("payment_method", "card")
        mobile_money_phone = request.POST.get("mobile_money_phone", "").strip()

        if payment_method not in {"card", "mobile_money", "fedapay"}:
            messages.error(request, "Veuillez sélectionner un mode de paiement valide.")
            return render(
                request,
                "orders/checkout.html",
                _checkout_context(cart, addresses, form),
            )

        if payment_method == "fedapay" and not settings.FEDAPAY_SECRET_KEY:
            messages.error(request, "Le paiement FedaPay n'est pas encore configuré.")
            return render(
                request,
                "orders/checkout.html",
                _checkout_context(cart, addresses, form),
            )

        if payment_method == "mobile_money" and not settings.MOBILE_MONEY_API_URL and not settings.DEBUG:
            messages.error(request, "Le paiement Mobile Money n'est pas encore configuré.")
            return render(
                request,
                "orders/checkout.html",
                _checkout_context(cart, addresses, form),
            )

        if payment_method == "mobile_money" and not mobile_money_phone:
            messages.error(request, "Veuillez renseigner un numéro de téléphone Mobile Money.")
            return render(
                request,
                "orders/checkout.html",
                _checkout_context(cart, addresses, form),
            )

        try:
            order = services.create_order_from_cart(
                request,
                address=address,
                email=request.user.email,
                payment_method=payment_method,
                mobile_money_phone=mobile_money_phone,
            )
        except ValueError:
            messages.error(request, "Votre panier est vide.")
            return redirect("cart:cart_detail")

        if payment_method == "card":
            checkout_url = create_checkout_session(request, order)
            return redirect(checkout_url)

        if payment_method == "fedapay":
            try:
                checkout_url = create_fedapay_checkout_url(request, order)
            except (requests.RequestException, ValueError):
                order.status = Order.Status.CANCELLED
                order.save(update_fields=["status", "updated_at"])
                messages.error(
                    request,
                    "Impossible d'initier le paiement FedaPay pour le moment. "
                    "Votre commande a été annulée, veuillez réessayer plus tard.",
                )
                return redirect("orders:order_detail", pk=order.pk)
            return redirect(checkout_url)

        try:
            initiate_mobile_money_payment(order)
        except (requests.RequestException, ValueError):
            order.status = Order.Status.CANCELLED
            order.save(update_fields=["status", "updated_at"])
            messages.error(
                request,
                "Impossible d'initier le paiement Mobile Money pour le moment. "
                "Votre commande a été annulée, veuillez réessayer plus tard.",
            )
            return redirect("orders:order_detail", pk=order.pk)

        return redirect("orders:order_success", pk=order.pk)

    return render(
        request,
        "orders/checkout.html",
        _checkout_context(cart, addresses, AddressForm()),
    )


@login_required
def order_success_view(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    return render(
        request,
        "orders/order_success.html",
        {
            "order": order,
            "can_confirm_mobile_money_locally": _can_confirm_mobile_money_locally(order),
        },
    )


@login_required
def order_history_view(request):
    orders = request.user.orders.order_by("-created_at")
    return render(request, "orders/order_history.html", {"orders": orders})


@login_required
def order_detail_view(request, pk):
    order = get_object_or_404(
        Order.objects.prefetch_related("items"), pk=pk, user=request.user
    )
    return render(
        request,
        "orders/order_detail.html",
        {
            "order": order,
            "can_confirm_mobile_money_locally": _can_confirm_mobile_money_locally(order),
        },
    )


@login_required
@require_POST
def confirm_mobile_money_locally_view(request, pk):
    if not settings.DEBUG:
        raise Http404("Confirmation locale indisponible.")

    order = get_object_or_404(Order, pk=pk, user=request.user)
    if not _can_confirm_mobile_money_locally(order):
        messages.warning(request, "Cette commande ne peut pas être confirmée localement.")
        return redirect("orders:order_detail", pk=order.pk)

    transaction_id = order.mobile_money_transaction_id or f"local-{order.pk}"
    order.mobile_money_transaction_id = transaction_id
    order.save(update_fields=["mobile_money_transaction_id", "updated_at"])
    fulfill_order(order, payment_intent_id=f"mobile_money:{transaction_id}")
    messages.success(
        request,
        "Paiement Mobile Money confirmé en local. La quittance a été générée et le mail envoyé.",
    )
    return redirect("orders:order_detail", pk=order.pk)


@login_required
def invoice_download_view(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    if not order.invoice_file:
        raise Http404("Aucune facture disponible pour cette commande.")

    response = FileResponse(order.invoice_file.open("rb"), as_attachment=True)
    response["Content-Disposition"] = f"attachment; filename={order.invoice_file.name.split('/')[-1]}"
    return response
