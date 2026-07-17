from django.conf import settings
from django.db import models

from catalog.models import ProductVariant


class Cart(models.Model):
    """
    A cart belongs either to a logged-in user, or to an anonymous session
    (identified by session_key). On login, the session cart is merged into
    the user's cart — see cart.services.merge_session_cart_into_user_cart.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cart",
    )
    session_key = models.CharField(max_length=40, null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "panier"
        verbose_name_plural = "paniers"

    def __str__(self):
        owner = self.user.email if self.user else f"session:{self.session_key}"
        return f"Panier de {owner}"

    @property
    def total_quantity(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self):
        return sum((item.line_total for item in self.items.all()), start=0)


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name="+")
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "article du panier"
        verbose_name_plural = "articles du panier"
        unique_together = ["cart", "variant"]

    def __str__(self):
        return f"{self.quantity} x {self.variant}"

    @property
    def line_total(self):
        return self.variant.price * self.quantity
