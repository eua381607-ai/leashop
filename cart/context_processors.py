def cart(request):
    return {"current_cart": request.cart}
