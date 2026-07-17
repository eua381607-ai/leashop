from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AddressForm, SignUpForm
from .models import Address


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("catalog:product_list")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Bienvenue sur LeaShop ! Ton compte a été créé.")
            return redirect("catalog:product_list")
    else:
        form = SignUpForm()

    return render(request, "accounts/signup.html", {"form": form})


@login_required
def profile_view(request):
    addresses = request.user.addresses.all()
    orders = request.user.orders.order_by("-created_at")[:10]
    return render(
        request,
        "accounts/profile.html",
        {"addresses": addresses, "orders": orders},
    )


@login_required
def address_create_view(request):
    if request.method == "POST":
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            messages.success(request, "Adresse ajoutée.")
            return redirect("accounts:profile")
    else:
        form = AddressForm()

    return render(request, "accounts/address_form.html", {"form": form})


@login_required
def address_update_view(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == "POST":
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, "Adresse mise à jour.")
            return redirect("accounts:profile")
    else:
        form = AddressForm(instance=address)

    return render(request, "accounts/address_form.html", {"form": form})


@login_required
def address_delete_view(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == "POST":
        address.delete()
        messages.success(request, "Adresse supprimée.")
    return redirect("accounts:profile")
