from django.contrib import admin

from inventory.models import InventoryItem, StockMovement


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("name", "quantity", "unit", "reorder_level", "cost_per_unit", "is_active")
    search_fields = ("name",)
    readonly_fields = ("quantity",)  # changed only through stock movements


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("created_at", "item", "change", "quantity_after", "reason", "reference")
    list_filter = ("reason",)
    list_select_related = ("item",)

    def has_change_permission(self, request, obj=None):
        return False  # the ledger is append-only

    def has_delete_permission(self, request, obj=None):
        return False
