from django.contrib import admin
from .models import Member
from .services import generate_reference_number


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('reference_number', 'full_name', 'phone_number', 'church', 'status')
    readonly_fields = ('reference_number',)

    def save_model(self, request, obj, form, change):
        if not obj.reference_number:
            obj.reference_number = generate_reference_number(obj.church_id)
        super().save_model(request, obj, form, change)
