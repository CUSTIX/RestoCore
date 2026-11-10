"""Staff-area sidebar. Each entry lists the roles that may see it; views enforce the same roles."""

from core.roles import ALL_ROLES, CASHIER, KITCHEN, MANAGEMENT, STAFF

NAV_ITEMS = [
    {"label": "Dashboard", "url": "dashboard:index", "roles": ALL_ROLES, "section": "dashboard"},
    {
        "label": "Bookings",
        "url": "bookings:list",
        "roles": (*MANAGEMENT, STAFF),
        "section": "bookings",
    },
    {
        "label": "Point of sale",
        "url": "sales:pos",
        "roles": (*MANAGEMENT, CASHIER),
        "section": "pos",
    },
    {
        "label": "Orders",
        "url": "sales:order_list",
        "roles": (*MANAGEMENT, CASHIER),
        "section": "orders",
    },
    {
        "label": "Kitchen",
        "url": "sales:kitchen",
        "roles": (*MANAGEMENT, KITCHEN),
        "section": "kitchen",
    },
    {"label": "Menu", "url": "sales:menu_list", "roles": MANAGEMENT, "section": "menu"},
    {
        "label": "Inventory",
        "url": "inventory:list",
        "roles": (*MANAGEMENT, KITCHEN),
        "section": "inventory",
    },
    {"label": "My work", "url": "staff:me", "roles": ALL_ROLES, "section": "me"},
    {
        "label": "Employees",
        "url": "staff:employee_list",
        "roles": MANAGEMENT,
        "section": "employees",
    },
    {"label": "Schedules", "url": "staff:shift_list", "roles": MANAGEMENT, "section": "shifts"},
    {
        "label": "Attendance",
        "url": "staff:attendance_list",
        "roles": MANAGEMENT,
        "section": "attendance",
    },
    {"label": "Leave", "url": "staff:leave_list", "roles": MANAGEMENT, "section": "leave"},
    {
        "label": "Payroll (demo)",
        "url": "payroll:period_list",
        "roles": ("Owner",),
        "section": "payroll",
    },
]
