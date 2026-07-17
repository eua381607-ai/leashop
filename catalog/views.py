from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ReviewForm
from .models import Category, Product


def product_list_view(request):
    products = Product.objects.filter(is_active=True).select_related("category")

    query = request.GET.get("q", "").strip()
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(sku__icontains=query)
        )

    category_slug = request.GET.get("category")
    active_category = None
    if category_slug:
        active_category = get_object_or_404(Category, slug=category_slug, is_active=True)
        products = products.filter(category=active_category)

    sort = request.GET.get("sort")
    sort_map = {
        "price_asc": "base_price",
        "price_desc": "-base_price",
        "newest": "-created_at",
    }
    products = products.order_by(sort_map.get(sort, "-created_at"))

    paginator = Paginator(products, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "page_obj": page_obj,
        "query": query,
        "active_category": active_category,
        "sort": sort or "newest",
    }
    return render(request, "catalog/product_list.html", context)


def category_detail_view(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    products = Product.objects.filter(is_active=True, category=category)
    paginator = Paginator(products, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "catalog/category_detail.html",
        {"category": category, "page_obj": page_obj},
    )


def product_detail_view(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related(
            "images", "variants", "reviews__user"
        ),
        slug=slug,
        is_active=True,
    )
    variants = product.variants.filter(is_active=True)
    reviews = product.reviews.select_related("user")

    user_review = None
    review_form = None
    if request.user.is_authenticated:
        user_review = reviews.filter(user=request.user).first()
        if request.method == "POST":
            review_form = ReviewForm(request.POST, instance=user_review)
            if review_form.is_valid():
                review = review_form.save(commit=False)
                review.product = product
                review.user = request.user
                review.save()
                messages.success(request, "Merci pour votre avis !")
                return redirect("catalog:product_detail", slug=product.slug)
        else:
            review_form = ReviewForm(instance=user_review)

    context = {
        "product": product,
        "variants": variants,
        "reviews": reviews,
        "review_form": review_form,
        "user_review": user_review,
    }
    return render(request, "catalog/product_detail.html", context)
