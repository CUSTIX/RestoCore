from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.forms import ThrottledAdminLoginForm
from accounts.models import User

admin.site.register(User, UserAdmin)

# Django admin has its own login page: give it the same brute-force throttling as the app.
admin.site.login_form = ThrottledAdminLoginForm
