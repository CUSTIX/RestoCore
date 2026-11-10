from django.db import migrations

ROLES = ("Owner", "Manager", "Cashier", "Kitchen", "Staff")  # frozen copy of core.roles


def create_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in ROLES:
        Group.objects.get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    # Reverse is a no-op: groups may already have members, so never delete them automatically.
    operations = [migrations.RunPython(create_groups, migrations.RunPython.noop)]
