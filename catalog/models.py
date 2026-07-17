from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField("nom", max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="catégorie parente",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField("active", default=True)

    class Meta:
        verbose_name = "catégorie"
        verbose_name_plural = "catégories"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalog:category_detail", kwargs={"slug": self.slug})


class Product(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products", verbose_name="catégorie"
    )
    name = models.CharField("nom", max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    sku = models.CharField("référence (SKU)", max_length=50, unique=True)
    description = models.TextField("description", blank=True)
    base_price = models.DecimalField(
        "prix de base",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Utilisé si la variante sélectionnée n'a pas de prix spécifique.",
    )
    is_active = models.BooleanField("actif", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "produit"
        verbose_name_plural = "produits"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["slug"]), models.Index(fields=["is_active"])]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                counter += 1
                slug = f"{base_slug}-{counter}"
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalog:product_detail", kwargs={"slug": self.slug})

    @property
    def primary_image(self):
        image = self.images.filter(is_primary=True).first()
        return image or self.images.first()

    @property
    def in_stock(self):
        return self.variants.filter(is_active=True, stock_quantity__gt=0).exists()

    @property
    def average_rating(self):
        agg = self.reviews.aggregate(models.Avg("rating"))
        return round(agg["rating__avg"] or 0, 1)

    @property
    def review_count(self):
        return self.reviews.count()

    def get_default_variant(self):
        return self.variants.filter(is_active=True).order_by("id").first()


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField("image", upload_to="products/%Y/%m/")
    alt_text = models.CharField("texte alternatif", max_length=200, blank=True)
    is_primary = models.BooleanField("image principale", default=False)
    position = models.PositiveIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "image produit"
        verbose_name_plural = "images produit"
        ordering = ["position", "id"]

    def __str__(self):
        return f"Image de {self.product.name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_primary:
            ProductImage.objects.filter(product=self.product).exclude(pk=self.pk).update(
                is_primary=False
            )


class ProductVariant(models.Model):
    """
    A purchasable unit of a product. Every product has at least one variant
    (even "simple" products get a single default variant), which is what
    carts and orders actually reference — this keeps stock tracking and
    pricing consistent regardless of whether the product has real options.
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    size = models.CharField("taille", max_length=50, blank=True)
    color = models.CharField("couleur", max_length=50, blank=True)
    sku_suffix = models.CharField("suffixe SKU", max_length=30, blank=True)
    price_override = models.DecimalField(
        "prix spécifique",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    stock_quantity = models.PositiveIntegerField("stock", default=0)
    is_active = models.BooleanField("active", default=True)

    class Meta:
        verbose_name = "variante"
        verbose_name_plural = "variantes"
        unique_together = ["product", "size", "color"]
        ordering = ["id"]

    def __str__(self):
        label = self.label
        return f"{self.product.name} — {label}" if label else self.product.name

    @property
    def label(self):
        parts = [p for p in (self.size, self.color) if p]
        return " / ".join(parts)

    @property
    def price(self):
        return self.price_override if self.price_override is not None else self.product.base_price

    @property
    def full_sku(self):
        return f"{self.product.sku}-{self.sku_suffix}" if self.sku_suffix else self.product.sku

    @property
    def is_in_stock(self):
        return self.is_active and self.stock_quantity > 0


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField(
        "note", validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField("commentaire", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "avis"
        verbose_name_plural = "avis"
        unique_together = ["product", "user"]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.rating}/5 par {self.user} sur {self.product.name}"
