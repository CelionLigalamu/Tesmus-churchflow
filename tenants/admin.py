from django.contrib import admin
from .models import Church, Region, Branch

@admin.register(Church)
class ChurchAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'slug', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'slug')
    prepopulated_fields = {'slug': ('name',)}


admin.site.register(Region)
admin.site.register(Branch)
