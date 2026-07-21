from decimal import Decimal
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

from accounts.models import Address, User
from cart.models import Cart, CartItem
from catalog.models import Category, Product, ProductVariant
from orders.models import Order
from orders.services import create_order_from_cart
from payments.services import fulfill_order, initiate_mobile_money_payment, process_mobile_money_callback


@override_settings(
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"],
    DEBUG=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    MOBILE_MONEY_API_URL="",
    SECURE_SSL_REDIRECT=False,
    STORAGES=TEST_STORAGES,
)
class CheckoutFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="client@example.com", password="Azerty123!")
        self.cart = Cart.objects.create(user=self.user)
        self.category = Category.objects.create(name="Électronique", slug="electronique")
        self.product = Product.objects.create(
            category=self.category,
            name="Casque audio",
            slug="casque-audio",
            sku="SKU-001",
            base_price=Decimal("89.90"),
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            stock_quantity=10,
            price_override=Decimal("89.90"),
        )
        CartItem.objects.create(cart=self.cart, variant=self.variant, quantity=2)
        self.address = Address.objects.create(
            user=self.user,
            full_name="Jean Dupont",
            phone_number="0123456789",
            address_line1="1 rue de la Paix",
            city="Cotonou",
            country="Bénin",
        )

    def test_create_order_from_cart_clears_the_cart_and_saves_the_order(self):
        request = SimpleNamespace(user=self.user, cart=self.cart)

        with self.captureOnCommitCallbacks(execute=True):
            order = create_order_from_cart(request, address=self.address, email=self.user.email)

        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())
        self.assertEqual(self.cart.items.count(), 0)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("paiement", mail.outbox[0].body.lower())

    def test_fulfill_order_generates_invoice_and_sends_confirmation(self):
        request = SimpleNamespace(user=self.user, cart=self.cart)
        with self.captureOnCommitCallbacks(execute=True):
            order = create_order_from_cart(request, address=self.address, email=self.user.email)

        with TemporaryDirectory() as tmpdir:
            with self.settings(MEDIA_ROOT=tmpdir):
                with self.captureOnCommitCallbacks(execute=True):
                    fulfill_order(order)

        self.assertEqual(order.status, Order.Status.PAID)
        self.assertTrue(order.invoice_file)
        self.assertTrue(order.invoice_file.name.endswith(".pdf"))
        self.assertIn("facture", order.invoice_file.name)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("facture", mail.outbox[1].body.lower())

    def test_mobile_money_callback_fulfills_order_like_stripe_webhook(self):
        request = SimpleNamespace(user=self.user, cart=self.cart)
        with self.captureOnCommitCallbacks(execute=True):
            order = create_order_from_cart(
                request,
                address=self.address,
                email=self.user.email,
                payment_method="mobile_money",
                mobile_money_phone="22997000000",
            )

        with TemporaryDirectory() as tmpdir:
            with self.settings(MEDIA_ROOT=tmpdir):
                with self.captureOnCommitCallbacks(execute=True):
                    processed = process_mobile_money_callback(
                        order,
                        transaction_id="mm-tx-001",
                        status="paid",
                    )

        order.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertTrue(processed)
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(order.mobile_money_transaction_id, "mm-tx-001")
        self.assertEqual(self.variant.stock_quantity, 8)
        self.assertTrue(order.invoice_file)
        self.assertEqual(len(mail.outbox), 2)

    @override_settings(
        MOBILE_MONEY_API_URL="https://provider.example/payments",
        MOBILE_MONEY_API_KEY="secret",
        SITE_BASE_URL="https://leashop.example",
        STRIPE_CURRENCY="xof",
    )
    @patch("payments.services.requests.post")
    def test_mobile_money_immediate_success_fulfills_order(self, post_mock):
        response = Mock()
        response.json.return_value = {"transaction_id": "mm-tx-002", "status": "success"}
        response.raise_for_status.return_value = None
        post_mock.return_value = response
        request = SimpleNamespace(user=self.user, cart=self.cart)
        with self.captureOnCommitCallbacks(execute=True):
            order = create_order_from_cart(
                request,
                address=self.address,
                email=self.user.email,
                payment_method="mobile_money",
                mobile_money_phone="22997000000",
            )

        with TemporaryDirectory() as tmpdir:
            with self.settings(MEDIA_ROOT=tmpdir):
                with self.captureOnCommitCallbacks(execute=True):
                    data = initiate_mobile_money_payment(order)

        order.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertEqual(data["transaction_id"], "mm-tx-002")
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(order.mobile_money_transaction_id, "mm-tx-002")
        self.assertEqual(order.stripe_payment_intent_id, "mobile_money:mm-tx-002")
        self.assertEqual(self.variant.stock_quantity, 8)

    def test_local_mobile_money_confirmation_generates_receipt_and_email(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.client.force_login(self.user)
        request = SimpleNamespace(user=self.user, cart=self.cart)
        with self.captureOnCommitCallbacks(execute=True):
            order = create_order_from_cart(
                request,
                address=self.address,
                email=self.user.email,
                payment_method="mobile_money",
                mobile_money_phone="22997000000",
            )

        with TemporaryDirectory() as tmpdir:
            with self.settings(MEDIA_ROOT=tmpdir):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.client.post(
                        reverse("orders:confirm_payment", args=[order.pk])
                    )

        order.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertRedirects(response, reverse("orders:order_success", args=[order.pk]))
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertTrue(order.invoice_file)
        self.assertIn("facture", order.invoice_file.name)
        self.assertEqual(self.variant.stock_quantity, 8)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[1].attachments[0][0], f"facture-LEASHOP-{order.pk:06d}.pdf")

    def test_checkout_with_no_selected_address_renders_the_form_instead_of_404ing(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("orders:checkout"),
            {
                "address_id": "",
                "full_name": "",
                "phone_number": "",
                "address_line1": "",
                "city": "",
                "country": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["new_address_form"].is_valid())
