from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserManager(BaseUserManager):
    """Custom manager: users are identified by email, not username."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("L'adresse email est obligatoire.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Un superuser doit avoir is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Un superuser doit avoir is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom user: login via email instead of username."""

    username = None
    email = models.EmailField("adresse email", unique=True)
    phone_number = models.CharField("téléphone", max_length=30, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email


class Address(models.Model):
    """A shipping/billing address, snapshot-able onto an order."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="addresses"
    )
    full_name = models.CharField("nom complet", max_length=150)
    phone_number = models.CharField("téléphone", max_length=30)
    address_line1 = models.CharField("adresse", max_length=255)
    address_line2 = models.CharField("complément", max_length=255, blank=True)
    city = models.CharField("ville", max_length=100)
    state = models.CharField("région / état", max_length=100, blank=True)
    postal_code = models.CharField("code postal", max_length=20, blank=True)
    country = models.CharField("pays", max_length=100)
    is_default = models.BooleanField("adresse par défaut", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "adresse"
        verbose_name_plural = "adresses"
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.full_name} — {self.city}, {self.country}"

    def save(self, *args, **kwargs):
        # Ensure only one default address per user.
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).exclude(
                pk=self.pk
            ).update(is_default=False)
        super().save(*args, **kwargs)
