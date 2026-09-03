from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Tesmus / Church', {'fields': ('is_tesmus_staff', 'church', 'scope_type', 'scope_region', 'scope_branch')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Tesmus / Church', {'fields': ('is_tesmus_staff', 'church', 'scope_type', 'scope_region', 'scope_branch')}),
    )
    list_display = ('username', 'email', 'is_tesmus_staff', 'church', 'scope_type', 'is_staff')


admin.site.register(User, CustomUserAdmin)