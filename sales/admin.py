from django.contrib import admin

from sales.models import (
    MenuCategory,
    MenuItem,
    Order,
    OrderLine,
    RecipeLine,
    SelfOrder,
    SelfOrderLine,
)


class RecipeLineInline(admin.TabularInline):
    model = RecipeLine
    extra = 1


@admin.register(MenuCategory)
class MenuCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order")


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "is_available")
    list_filter = ("category", "is_available")
    search_fields = ("name",)
    inlines = [RecipeLineInline]


class OrderLineInline(admin.TabularInline):
    model = OrderLine
    extra = 0
    readonly_fields = ("menu_item", "name", "unit_price", "quantity", "line_total")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Read-only: orders change only through the POS so stock stays consistent."""

    list_display = ("id", "created_at", "status", "kitchen_status", "total", "cashier")
    list_filter = ("status", "kitchen_status", "payment_method")
    inlines = [OrderLineInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class SelfOrderLineInline(admin.TabularInline):
    model = SelfOrderLine
    extra = 0
    readonly_fields = ("menu_item", "name", "unit_price", "quantity", "line_total")
    can_delete = False


@admin.register(SelfOrder)
class SelfOrderAdmin(admin.ModelAdmin):
    """Read-only: customer orders change only through the ordering pages and the POS."""

    list_display = ("code", "created_at", "status", "order_type", "table_label", "total", "order")
    list_filter = ("status", "order_type")
    search_fields = ("code",)
    inlines = [SelfOrderLineInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
