from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from .models import User


class MemberMatchesChurchMixin:
    """A sign-in may only be linked to a member of its own church."""

    def clean(self):
        cleaned = super().clean()
        member, church = cleaned.get('member'), cleaned.get('church')
        if member and (church is None or member.church_id != church.id):
            self.add_error('member', 'Choose a member of the same church as this sign-in.')
        return cleaned


class ChurchUserChangeForm(MemberMatchesChurchMixin, UserChangeForm):
    pass


# Built on the admin's own creation form, which has the "Password-based authentication"
# choice (usable_password) that the admin's add page lists.
class ChurchUserCreationForm(MemberMatchesChurchMixin, AdminUserCreationForm):
    pass


class CustomUserAdmin(UserAdmin):
    form = ChurchUserChangeForm
    add_form = ChurchUserCreationForm
    raw_id_fields = ('member',)
    fieldsets = UserAdmin.fieldsets + (
        ('Tesmus / Church', {'fields': ('is_tesmus_staff', 'church', 'scope_type', 'scope_region', 'is_usher', 'member')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Tesmus / Church', {'fields': ('is_tesmus_staff', 'church', 'scope_type', 'scope_region', 'is_usher', 'member')}),
    )
    list_display = ('username', 'email', 'is_tesmus_staff', 'church', 'scope_type', 'is_usher', 'is_staff')
    list_filter = UserAdmin.list_filter + ('is_usher', 'church')


admin.site.register(User, CustomUserAdmin)