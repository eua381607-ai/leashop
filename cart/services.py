from .models import Cart, CartItem


def resolve_cart(cart):
    resolver = getattr(cart, "_resolve", None)
    if callable(resolver):
        return resolver()
    return cart


def get_or_create_cart(request):
    """Returns the Cart tied to the current user (if authenticated) or the
    current session (anonymous). Always available via request.cart thanks
    to CartMiddleware, but exposed here too for direct use."""
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart

    if not request.session.session_key:
        request.session.create()
    
    if not request.session.get("cart_init"):
        request.session["cart_init"] = True

    session_key = request.session.session_key
    cart, _ = Cart.objects.get_or_create(session_key=session_key, user=None)
    return cart


def add_item(cart, variant, quantity=1):
    cart = resolve_cart(cart)
    item, created = CartItem.objects.get_or_create(cart=cart, variant=variant)
    if not created:
        item.quantity += quantity
    else:
        item.quantity = quantity
    item.quantity = min(item.quantity, variant.stock_quantity or item.quantity)
    item.save()
    return item


def update_item_quantity(cart, item_id, quantity):
    cart = resolve_cart(cart)
    item = cart.items.filter(pk=item_id).first()
    if not item:
        return None
    if quantity <= 0:
        item.delete()
        return None
    item.quantity = min(quantity, item.variant.stock_quantity or quantity)
    item.save()
    return item


def remove_item(cart, item_id):
    cart = resolve_cart(cart)
    cart.items.filter(pk=item_id).delete()


def merge_session_cart_into_user_cart(request, user):
    """Called right after login: folds the anonymous session cart into the
    user's persistent cart, summing quantities on conflicts."""
    session_key = request.session.session_key
    if not session_key:
        return

    try:
        session_cart = Cart.objects.get(session_key=session_key, user__isnull=True)
    except Cart.DoesNotExist:
        return

    user_cart, _ = Cart.objects.get_or_create(user=user)

    for item in session_cart.items.all():
        existing = user_cart.items.filter(variant=item.variant).first()
        if existing:
            existing.quantity += item.quantity
            existing.save()
        else:
            item.cart = user_cart
            item.save()

    session_cart.delete()
