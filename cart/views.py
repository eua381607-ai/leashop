from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from catalog.models import ProductVariant

from . import services


def cart_detail_view(request):
    cart = request.cart
    return render(request, "cart/cart_detail.html", {"cart": cart})


@require_POST
def cart_add_view(request, variant_id):
    variant = get_object_or_404(ProductVariant, pk=variant_id, is_active=True)
    quantity = int(request.POST.get("quantity", 1))

    if not variant.is_in_stock:
        messages.error(request, "Cet article n'est plus en stock.")
        return redirect(request.META.get("HTTP_REFERER", "catalog:product_list"))

    services.add_item(request.cart, variant, quantity=quantity)
    messages.success(request, f"« {variant.product.name} » ajouté au panier.")
    return redirect(request.META.get("HTTP_REFERER") or reverse("cart:cart_detail"))


@require_POST
def cart_update_view(request, item_id):
    quantity = int(request.POST.get("quantity", 1))
    services.update_item_quantity(request.cart, item_id, quantity)
    return redirect("cart:cart_detail")


@require_POST
def cart_remove_view(request, item_id):
    services.remove_item(request.cart, item_id)
    messages.info(request, "Article retiré du panier.")
    return redirect("cart:cart_detail")
