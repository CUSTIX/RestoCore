from django.core.paginator import Paginator

DEFAULT_PER_PAGE = 20


def paginate(request, queryset, per_page: int = DEFAULT_PER_PAGE):
    """Return the requested page. Invalid or out-of-range page numbers fall back safely."""
    return Paginator(queryset, per_page).get_page(request.GET.get("page"))
