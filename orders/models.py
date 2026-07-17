import uuid

from django.conf import settings
from django.db import models

from catalog.models import ProductVariant


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente de paiement"
        PAID = "paid", "Payée"
        SHIPPED = "shipped", "Expédiée"
        DELIVERED = "delivered", "Livrée"
        CANCELLED = "cancelled", "Annulée"
        REFUNDED = "refunded", "Remboursée"
        fedapay_transaction_id=uuid.uuid4().hex

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="orders",
    )
    email = models.EmailField("email de contact")
    status = models.CharField(
        "statut", max_length=50, choices=Status.choices, default=Status.PENDING
    )

    # Shipping address snapshot (kept even if the Address object is later
    # edited or deleted, so historical orders stay accurate).
    shipping_full_name = models.CharField(max_length=150)
    shipping_phone_number = models.CharField(max_length=30)
    shipping_address_line1 = models.CharField(max_length=255)
    shipping_address_line2 = models.CharField(max_length=255, blank=True)
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100, blank=True)
    shipping_postal_code = models.CharField(max_length=20, blank=True)
    shipping_country = models.CharField(max_length=100)

    subtotal_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    stripe_checkout_session_id = models.CharField(max_length=255, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    payment_method = models.CharField(
        "mode de paiement",
        max_length=20,
        choices=[
            ("card", "Carte bancaire"),
            ("mobile_money", "Mobile Money"),
            ("fedapay", "FedaPay"),
        ],
        default="card",
    )
    mobile_money_phone = models.CharField(max_length=30, blank=True)
    mobile_money_transaction_id = models.CharField(max_length=255, blank=True)
    fedapay_transaction_id = models.CharField(max_length=255, blank=True)
    fedapay_reference = models.CharField(max_length=255, blank=True)
    fedapay_payment_url = models.URLField(max_length=500, blank=True)
    invoice_file = models.FileField(
        upload_to="invoices/%Y/%m/", blank=True, null=True, verbose_name="facture"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "commande"
        verbose_name_plural = "commandes"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Commande #{self.pk} ({self.get_status_display()})"

    def mark_as_paid(self, payment_intent_id=""):
        self.status = Order.Status.PAID
        if payment_intent_id:
            self.stripe_payment_intent_id = payment_intent_id
        self.save(update_fields=["status", "stripe_payment_intent_id", "updated_at"])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    # Snapshots — survive product edits/deletions, and record price paid.
    product_name = models.CharField(max_length=200)
    variant_label = models.CharField(max_length=100, blank=True)
    sku = models.CharField(max_length=80)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "article commandé"
        verbose_name_plural = "articles commandés"

    def __str__(self):
        return f"{self.quantity} x {self.product_name}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity
