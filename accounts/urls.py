from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup_view, name="signup"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="accounts/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("profile/", views.profile_view, name="profile"),
    path("addresses/add/", views.address_create_view, name="address_add"),
    path("addresses/<int:pk>/edit/", views.address_update_view, name="address_edit"),
    path("addresses/<int:pk>/delete/", views.address_delete_view, name="address_delete"),
    path(
        "password-change/",
        auth_views.PasswordChangeView.as_view(
            template_name="accounts/password_change.html",
            success_url="/accounts/profile/",
        ),
        name="password_change",
    ),
]
