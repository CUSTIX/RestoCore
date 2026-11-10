from decimal import Decimal

from django.db import migrations

# DEMO placeholders only. Not any country's real contribution or tax rates.
DEMO_RATES = [
    ("Social security (demo)", Decimal("0.0450")),
    ("Health insurance (demo)", Decimal("0.0250")),
    ("Housing fund (demo)", Decimal("0.0200")),
    ("Income tax withholding (demo)", Decimal("0.0800")),
]


def add_rates(apps, schema_editor):
    DeductionRate = apps.get_model("payroll", "DeductionRate")
    for name, rate in DEMO_RATES:
        DeductionRate.objects.get_or_create(name=name, defaults={"rate": rate})


class Migration(migrations.Migration):
    dependencies = [("payroll", "0001_initial")]

    operations = [migrations.RunPython(add_rates, migrations.RunPython.noop)]
