"""Staff-area sidebar. Each entry lists the roles that may see it; views enforce the same roles."""

from core.roles import ALL_ROLES, CASHIER, KITCHEN, MANAGEMENT, OWNER, STAFF


def _item(label, url, roles, section, icon, group):
    return {
        "label": label,
        "url": url,
        "roles": roles,
        "section": section,
        "icon": icon,
        "group": group,
    }


NAV_ITEMS = [
    _item("Dashboard", "dashboard:index", ALL_ROLES, "dashboard", "dashboard", "Overview"),
    _item("Bookings", "bookings:list", (*MANAGEMENT, STAFF), "bookings", "calendar", "Service"),
    _item("Point of sale", "sales:pos", (*MANAGEMENT, CASHIER), "pos", "pos", "Service"),
    _item("Orders", "sales:order_list", (*MANAGEMENT, CASHIER), "orders", "receipt", "Service"),
    _item("Kitchen", "sales:kitchen", (*MANAGEMENT, KITCHEN), "kitchen", "flame", "Service"),
    _item("Menu", "sales:menu_list", MANAGEMENT, "menu", "book", "Back of house"),
    _item(
        "Inventory",
        "inventory:list",
        (*MANAGEMENT, KITCHEN),
        "inventory",
        "package",
        "Back of house",
    ),
    _item("My work", "staff:me", ALL_ROLES, "me", "user", "Team"),
    _item("Employees", "staff:employee_list", MANAGEMENT, "employees", "users", "Team"),
    _item("Schedules", "staff:shift_list", MANAGEMENT, "shifts", "calendar", "Team"),
    _item("Attendance", "staff:attendance_list", MANAGEMENT, "attendance", "clock", "Team"),
    _item("Leave", "staff:leave_list", MANAGEMENT, "leave", "sun", "Team"),
    _item("Payroll (demo)", "payroll:period_list", (OWNER,), "payroll", "wallet", "Admin"),
]
