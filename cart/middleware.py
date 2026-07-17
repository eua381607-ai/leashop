from .services import get_or_create_cart


class CartMiddleware:
    """Attaches request.cart (a Cart instance) to every request, so views
    and templates never have to look it up manually."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.cart = SimpleCartProxy(request)
        return self.get_response(request)


class SimpleCartProxy:
    """Lazily resolves the cart on first access to avoid a DB hit on every
    single request (e.g. static asset requests, admin pages)."""

    def __init__(self, request):
        self._request = request
        self._cart = None

    def _resolve(self):
        if self._cart is None:
            self._cart = get_or_create_cart(self._request)
        return self._cart

    def __getattr__(self, item):
        return getattr(self._resolve(), item)
