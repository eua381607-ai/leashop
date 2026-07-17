from .models import Category


def categories(request):
    """Makes the active top-level categories available in every template
    (used for the navbar dropdown)."""
    return {
        "nav_categories": Category.objects.filter(is_active=True, parent__isnull=True)
    }
