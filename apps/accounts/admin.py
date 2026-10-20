from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class RestoCoreUserAdmin(UserAdmin):
    add_fieldsets = UserAdmin.add_fieldsets + (("Contact", {"fields": ("email",)}),)
