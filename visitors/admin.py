from django.contrib import admin
from .models import Visitor
from .services import convert_visitor_to_member


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone_number', 'church', 'converted_to_member')
    actions = ['convert_to_member']

    def convert_to_member(self, request, queryset):
        count = 0
        for visitor in queryset:
            if not visitor.converted_to_member_id:
                convert_visitor_to_member(visitor)
                count += 1
        self.message_user(request, f"{count} visitor(s) converted to member.")
    convert_to_member.short_description = "Convert selected visitors to members"
