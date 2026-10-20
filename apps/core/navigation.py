"""Permission-aware internal navigation registry."""

NAVIGATION_ITEMS = (
    {"label": "Overview", "url_name": "core:workspace", "permission": "core.access_internal"},
    {"label": "Bookings", "url_name": "bookings:home", "permission": "bookings.access_bookings"},
    {"label": "Orders", "url_name": "orders:home", "permission": "orders.access_orders"},
    {
        "label": "Inventory",
        "url_name": "inventory:home",
        "permission": "inventory.access_inventory",
    },
    {"label": "Staff", "url_name": "staff:home", "permission": "staff.access_staff"},
    {"label": "Payroll", "url_name": "payroll:home", "permission": "payroll.access_payroll"},
    {"label": "POS", "url_name": "pos:home", "permission": "pos.access_pos"},
    {"label": "Reports", "url_name": "reports:home", "permission": "reports.access_reports"},
)
