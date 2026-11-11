"""Fill the database with fake demo data (Faker). Never real people or real payroll.

Usage: python manage.py seed_demo
Every demo account uses the password in DEMO_PASSWORD (default "restocore-demo").
"""

import datetime as dt
import os
import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from faker import Faker

from bookings import services as booking_services
from bookings.models import Booking
from inventory import services as inventory_services
from inventory.services import InsufficientStock
from payroll import services as payroll_services
from sales import services as sales_services
from sales.models import MenuCategory, MenuItem, Order, RecipeLine
from staff import services as staff_services
from staff.models import LeaveRequest, Shift, TimeEntry

D = Decimal

ACCOUNTS = [  # username, role, position, hourly rate
    ("owner", "Owner", "Owner", D("0")),
    ("manager", "Manager", "Restaurant manager", D("260")),
    ("cashier", "Cashier", "Cashier", D("120")),
    ("kitchen", "Kitchen", "Head cook", D("150")),
    ("staff", "Staff", "Server", D("110")),
    ("cashier2", "Cashier", "Cashier", D("115")),
    ("kitchen2", "Kitchen", "Line cook", D("130")),
    ("staff2", "Staff", "Server", D("105")),
    ("staff3", "Staff", "Host", D("105")),
]

INGREDIENTS = [  # name, unit, quantity, reorder level, cost per unit
    ("Coffee beans", "kg", "8", "2", "950"),
    ("Milk", "l", "30", "8", "95"),
    ("Oat milk", "l", "10", "3", "180"),
    ("Cream", "l", "8", "2", "260"),
    ("Matcha powder", "kg", "0.4", "0.5", "2400"),
    ("Condensed milk", "l", "6", "2", "150"),
    ("Sea salt", "kg", "2", "0.5", "60"),
    ("Sugar", "kg", "10", "2", "70"),
    ("Oranges", "kg", "10", "3", "110"),
    ("Calamansi", "kg", "3", "1", "120"),
    ("Sourdough bread", "pcs", "40", "10", "45"),
    ("Avocado", "pcs", "40", "10", "55"),
    ("Eggs", "pcs", "240", "60", "9"),
    ("Flour", "kg", "12", "3", "60"),
    ("Butter", "kg", "6", "2", "480"),
    ("Chocolate", "kg", "4", "1", "450"),
    ("Mixed berries", "kg", "4", "1", "420"),
    ("Mango", "kg", "8", "3", "150"),
    ("Cookies", "kg", "3", "1", "300"),
    ("Chicken thigh", "kg", "20", "6", "220"),
    ("Rice", "kg", "30", "8", "55"),
    ("Garlic", "kg", "4", "1", "180"),
    ("Pasta", "kg", "8", "2", "140"),
    ("Cheese", "kg", "3", "1", "520"),
    ("Lettuce", "kg", "4", "2", "160"),
    ("Tomato", "kg", "6", "2", "90"),
]

PHOTO = "website/img/dishes/{}.jpg"

# category: [(name, description, price, photo, signature, [(ingredient, qty per portion)])]
MENU = {
    "Coffee": [
        (
            "Espresso",
            "Double shot of our house blend: dark chocolate, toasted nuts",
            "110",
            "espresso",
            False,
            [("Coffee beans", "0.018")],
        ),
        (
            "Cortado",
            "Equal parts espresso and silky milk",
            "140",
            "cortado",
            False,
            [("Coffee beans", "0.018"), ("Milk", "0.06")],
        ),
        (
            "Flat white",
            "Velvety microfoam over a ristretto double",
            "160",
            "flat-white",
            False,
            [("Coffee beans", "0.018"), ("Milk", "0.15")],
        ),
        (
            "Cappuccino",
            "Classic, with a cloud of foam",
            "155",
            "cappuccino",
            False,
            [("Coffee beans", "0.018"), ("Milk", "0.15")],
        ),
        (
            "Spanish latte",
            "Espresso, milk and a ribbon of condensed milk",
            "175",
            "spanish-latte",
            True,
            [("Coffee beans", "0.018"), ("Milk", "0.18"), ("Condensed milk", "0.03")],
        ),
        (
            "Iced sea-salt latte",
            "Cold milk, espresso and salted cream cap",
            "185",
            "iced-sea-salt-latte",
            True,
            [("Coffee beans", "0.018"), ("Milk", "0.18"), ("Cream", "0.04"), ("Sea salt", "0.002")],
        ),
        (
            "Single-origin pour-over",
            "Hand-brewed V60, rotating local beans",
            "190",
            "pour-over",
            False,
            [("Coffee beans", "0.020")],
        ),
        (
            "Brewed coffee",
            "Bottomless before 10 am",
            "95",
            "brewed-coffee",
            False,
            [("Coffee beans", "0.015")],
        ),
    ],
    "Not coffee": [
        (
            "Ceremonial matcha latte",
            "Whisked to order, with oat milk",
            "195",
            "matcha-latte",
            True,
            [("Matcha powder", "0.004"), ("Oat milk", "0.2")],
        ),
        (
            "Fresh orange juice",
            "Squeezed to order",
            "135",
            "orange-juice",
            False,
            [("Oranges", "0.35")],
        ),
        (
            "Calamansi spritz",
            "Calamansi, honey, sparkling water and mint",
            "145",
            "calamansi-spritz",
            False,
            [("Calamansi", "0.06"), ("Sugar", "0.02")],
        ),
    ],
    "All-day brunch": [
        (
            "Smashed avocado toast",
            "Sourdough, soft eggs, chili flakes, lemon",
            "265",
            "avocado-toast",
            True,
            [("Sourdough bread", "1"), ("Avocado", "1"), ("Eggs", "1")],
        ),
        (
            "Sunny egg sourdough",
            "Fried egg, garlic butter, herbs",
            "185",
            "egg-sourdough",
            False,
            [("Sourdough bread", "1"), ("Eggs", "1"), ("Butter", "0.01")],
        ),
        (
            "Buttermilk pancakes",
            "Three fluffy stacks, berries, maple, banana",
            "245",
            "pancakes",
            True,
            [("Flour", "0.12"), ("Eggs", "1"), ("Milk", "0.10"), ("Mixed berries", "0.04")],
        ),
        (
            "Chicken adobo rice bowl",
            "Soy-vinegar chicken, garlic rice, pickles",
            "285",
            "adobo-rice-bowl",
            False,
            [("Chicken thigh", "0.22"), ("Rice", "0.20"), ("Garlic", "0.02")],
        ),
        (
            "Creamy carbonara",
            "Fettuccine, cream, egg yolk, aged cheese",
            "295",
            "carbonara",
            False,
            [("Pasta", "0.15"), ("Cream", "0.10"), ("Eggs", "1"), ("Cheese", "0.03")],
        ),
        (
            "Garden salad",
            "Greens, cherry tomato, avocado, citrus dressing",
            "220",
            "garden-salad",
            False,
            [("Lettuce", "0.12"), ("Tomato", "0.08")],
        ),
    ],
    "Pastries & sweets": [
        (
            "Butter croissant",
            "Laminated over three days, baked every morning",
            "120",
            "croissant",
            True,
            [("Flour", "0.06"), ("Butter", "0.04")],
        ),
        (
            "Sourdough loaf",
            "Naturally leavened, to take home",
            "260",
            "sourdough-loaf",
            False,
            [("Flour", "0.5")],
        ),
        (
            "Fruit tarts",
            "Vanilla custard, seasonal fruit",
            "130",
            "fruit-tarts",
            False,
            [("Flour", "0.04"), ("Mixed berries", "0.03"), ("Eggs", "1")],
        ),
        (
            "Dark chocolate cake",
            "Three layers, ganache drip",
            "195",
            "chocolate-cake",
            False,
            [("Chocolate", "0.06"), ("Flour", "0.05"), ("Eggs", "1")],
        ),
        (
            "Fudge brownie",
            "Warm, with chocolate sauce",
            "145",
            "fudge-brownie",
            False,
            [("Chocolate", "0.05"), ("Flour", "0.03"), ("Sugar", "0.03")],
        ),
        (
            "Cookies & cream parfait",
            "Chocolate mousse, crushed cookies, cream",
            "175",
            "cookies-cream-parfait",
            False,
            [("Cookies", "0.05"), ("Cream", "0.08")],
        ),
        (
            "Mango gelato",
            "Carabao mango, churned in house",
            "140",
            "mango-gelato",
            False,
            [("Mango", "0.12"), ("Milk", "0.10"), ("Sugar", "0.02")],
        ),
    ],
}


class Command(BaseCommand):
    help = "Create fake demo data for every RestoCore module."

    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.filter(username="owner").exists():
            raise CommandError(
                "Demo data already exists (user 'owner'). Reset the database "
                "first: docker compose down -v"
            )
        password = os.environ.get("DEMO_PASSWORD", "restocore-demo")
        self.fake = Faker()
        Faker.seed(2024)
        random.seed(2024)
        self.today = timezone.localdate()

        with transaction.atomic():
            employees = self._accounts(password)
            items = self._inventory(employees["owner"].user)
            self._menu(items)
            self._orders(employees)
            self._bookings()
            self._shifts_and_attendance(employees)
            self._leave(employees)
            self._payroll(employees["owner"].user)

        self.stdout.write(self.style.SUCCESS("Demo data created."))
        self.stdout.write(
            f"Log in at /accounts/login/ with any of: "
            f"{', '.join(a[0] for a in ACCOUNTS)}. Password: {password}"
        )

    # -- people --------------------------------------------------------------------------
    def _accounts(self, password):
        User = get_user_model()
        root = User.objects.create_superuser("system-seed", password=None)  # temp actor
        root.set_unusable_password()
        root.save()
        employees = {}
        for username, role, position, rate in ACCOUNTS:
            first, last = self.fake.first_name(), self.fake.last_name()
            employees[username] = staff_services.create_employee(
                actor=root,
                username=username,
                password=password,
                first_name=first,
                last_name=last,
                email=f"{username}@example.com",
                role=role,
                position=position,
                phone=self.fake.numerify("0917 ### ####"),
                hourly_rate=rate,
                hire_date=self.today - dt.timedelta(days=random.randint(60, 900)),
            )
        owner = employees["owner"].user
        owner.is_staff = owner.is_superuser = True  # owner can also use /admin/
        owner.save(update_fields=["is_staff", "is_superuser"])
        root.delete()
        return employees

    # -- inventory & menu ----------------------------------------------------------------
    def _inventory(self, user):
        items = {}
        for name, unit, qty, reorder, cost in INGREDIENTS:
            # Start high so a week of seeded sales still leaves realistic levels.
            start_qty = D(qty) * 3 if name != "Matcha powder" else D(qty)
            items[name] = inventory_services.create_item(
                user=user,
                name=name,
                unit=unit,
                quantity=start_qty,
                reorder_level=D(reorder),
                cost_per_unit=D(cost),
                is_active=True,
            )
        return items

    def _menu(self, items):
        for order, (cat_name, dishes) in enumerate(MENU.items()):
            cat = MenuCategory.objects.create(name=cat_name, sort_order=order)
            for name, desc, price, photo, signature, recipe in dishes:
                dish = MenuItem.objects.create(
                    category=cat,
                    name=name,
                    description=desc,
                    price=D(price),
                    photo=PHOTO.format(photo),
                    is_signature=signature,
                )
                RecipeLine.objects.bulk_create(
                    [
                        RecipeLine(menu_item=dish, inventory_item=items[ing], quantity=D(q))
                        for ing, q in recipe
                    ]
                )

    # -- sales ---------------------------------------------------------------------------
    def _orders(self, employees):
        cashiers = [
            employees["cashier"].user,
            employees["cashier2"].user,
            employees["manager"].user,
        ]
        menu = list(MenuItem.objects.exclude(name="Ceremonial matcha latte"))  # matcha stays low
        tz = timezone.get_current_timezone()
        for days_ago in range(6, -1, -1):
            day = self.today - dt.timedelta(days=days_ago)
            for _ in range(random.randint(6, 10) if days_ago else 6):
                picks = random.sample(menu, random.randint(1, 4))
                quantities = {m.pk: random.randint(1, 3) for m in picks}
                lines, subtotal, tax, total = sales_services.price_lines(quantities)
                dine_in = random.random() < 0.7
                cash = random.random() < 0.6
                try:
                    order = sales_services.place_order(
                        quantities=quantities,
                        cashier=random.choice(cashiers),
                        order_type="dine_in" if dine_in else "takeaway",
                        table_label=f"T{random.randint(1, 12)}" if dine_in else "",
                        payment_method="cash" if cash else "card",
                        amount_tendered=(total + random.choice([0, 20, 50, 100])) if cash else None,
                    )
                except InsufficientStock:
                    continue
                when = dt.datetime.combine(
                    day, dt.time(random.randint(11, 20), random.randint(0, 59)), tzinfo=tz
                )
                if days_ago == 0:
                    when = min(when, timezone.now() - dt.timedelta(minutes=5))
                kitchen = "served"
                if days_ago == 0:
                    kitchen = random.choice(["queued", "preparing", "ready", "served", "served"])
                Order.objects.filter(pk=order.pk).update(created_at=when, kitchen_status=kitchen)
            if days_ago in (2, 4):  # one voided order on some days, ingredients returned
                victim = Order.objects.filter(
                    created_at__date=day, status=Order.Status.PAID
                ).first()
                if victim:
                    Order.objects.filter(pk=victim.pk).update(kitchen_status="queued")
                    victim.refresh_from_db()
                    sales_services.void_order(
                        victim, user=employees["manager"].user, reason="Customer changed their mind"
                    )

    # -- bookings ------------------------------------------------------------------------
    def _bookings(self):
        slots = booking_services.time_slots()
        for days_ahead in range(-3, 8):
            day = self.today + dt.timedelta(days=days_ahead)
            for _ in range(random.randint(3, 7)):
                if days_ahead < 0:
                    status = random.choice(["completed", "completed", "no_show", "cancelled"])
                elif days_ahead == 0:
                    status = random.choice(["confirmed", "seated", "pending"])
                else:
                    status = random.choice(["pending", "confirmed", "confirmed"])
                Booking.objects.create(  # direct create: seed includes past bookings
                    name=self.fake.name(),
                    phone=self.fake.numerify("0918 ### ####"),
                    email=self.fake.free_email() if random.random() < 0.6 else "",
                    party_size=random.randint(2, 8),
                    date=day,
                    time=random.choice(slots),
                    status=status,
                    source=random.choice(["website", "staff"]),
                    notes=random.choice(
                        [
                            "",
                            "",
                            "Birthday celebration",
                            "Window seat please",
                            "One vegetarian guest",
                        ]
                    ),
                )

    # -- staff ---------------------------------------------------------------------------
    def _shifts_and_attendance(self, employees):
        tz = timezone.get_current_timezone()
        workers = [e for k, e in employees.items() if k != "owner"]
        for days in range(-14, 8):
            day = self.today + dt.timedelta(days=days)
            for i, emp in enumerate(workers):
                if (days + i) % 7 == 0:  # one day off a week
                    continue
                start = dt.time(10, 0) if i % 2 == 0 else dt.time(14, 0)
                end = dt.time(18, 0) if i % 2 == 0 else dt.time(22, 0)
                Shift.objects.create(employee=emp, date=day, start_time=start, end_time=end)
                if days < 0:
                    clock_in = dt.datetime.combine(day, start, tzinfo=tz) + dt.timedelta(
                        minutes=random.randint(-10, 15)
                    )
                    clock_out = dt.datetime.combine(day, end, tzinfo=tz) + dt.timedelta(
                        minutes=random.randint(-5, 30)
                    )
                    TimeEntry.objects.create(employee=emp, clock_in=clock_in, clock_out=clock_out)
        # A few people are on shift right now.
        for key in ("cashier", "kitchen", "staff"):
            TimeEntry.objects.create(
                employee=employees[key], clock_in=timezone.now() - dt.timedelta(hours=2)
            )

    def _leave(self, employees):
        LeaveRequest.objects.create(
            employee=employees["staff2"],
            leave_type="vacation",
            start_date=self.today + dt.timedelta(days=10),
            end_date=self.today + dt.timedelta(days=12),
            reason="Family trip",
        )
        LeaveRequest.objects.create(
            employee=employees["kitchen2"],
            leave_type="personal",
            start_date=self.today + dt.timedelta(days=5),
            end_date=self.today + dt.timedelta(days=5),
            reason="Appointment",
        )
        LeaveRequest.objects.create(
            employee=employees["cashier2"],
            leave_type="sick",
            start_date=self.today - dt.timedelta(days=9),
            end_date=self.today - dt.timedelta(days=8),
            reason="Flu",
            status="approved",
            reviewed_by=employees["manager"].user,
            reviewed_at=timezone.now(),
        )
        LeaveRequest.objects.create(
            employee=employees["staff3"],
            leave_type="vacation",
            start_date=self.today + dt.timedelta(days=2),
            end_date=self.today + dt.timedelta(days=3),
            reason="Short break",
            status="rejected",
            reviewed_by=employees["manager"].user,
            reviewed_at=timezone.now(),
            review_note="Short-staffed that weekend, please pick other dates",
        )

    # -- payroll -------------------------------------------------------------------------
    def _payroll(self, owner):
        start = self.today - dt.timedelta(days=14)
        period = payroll_services.create_period(
            start_date=start, end_date=self.today - dt.timedelta(days=1), user=owner
        )
        payroll_services.generate_payslips(period)
