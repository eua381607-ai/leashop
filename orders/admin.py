from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product_name", "variant_label", "sku", "unit_price", "quantity"]
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "email", "status", "payment_method", "total_amount", "created_at"]
    list_filter = ["status", "payment_method", "created_at"]
    search_fields = [
        "email",
        "id",
        "stripe_checkout_session_id",
        "fedapay_transaction_id",
        "fedapay_reference",
    ]
    inlines = [OrderItemInline]
    readonly_fields = [
        "stripe_checkout_session_id",
        "stripe_payment_intent_id",
        "fedapay_transaction_id",
        "fedapay_reference",
        "fedapay_payment_url",
        "subtotal_amount",
        "total_amount",
    ]
