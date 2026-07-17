from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .services import merge_session_cart_into_user_cart


@receiver(user_logged_in)
def merge_cart_on_login(sender, request, user, **kwargs):
    merge_session_cart_into_user_cart(request, user)
