from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Tesmus / Church', {'fields': ('is_tesmus_staff', 'church')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Tesmus / Church', {'fields': ('is_tesmus_staff', 'church')}),
    )
    list_display = ('username', 'email', 'is_tesmus_staff', 'church', 'is_staff')


admin.site.register(User, CustomUserAdmin)
