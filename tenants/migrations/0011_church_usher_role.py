import django.db.models.deletion
from django.db import migrations, models


def choose_usher_role(apps, schema_editor):
    """Existing churches start with their own "Ushers" ministry role, when they have one."""
    Church = apps.get_model('tenants', 'Church')
    MinistryRole = apps.get_model('members', 'MinistryRole')
    for church in Church.objects.filter(usher_role__isnull=True):
        role = MinistryRole.objects.filter(church=church, name__iexact='ushers').first()
        if role:
            church.usher_role = role
            church.save(update_fields=['usher_role'])


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0008_remove_member_branch'),
        ('tenants', '0010_church_registration_heading_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='church',
            name='usher_role',
            field=models.ForeignKey(blank=True, help_text="Members with this ministry role are the church's ushers. New usher sign-ins get this role automatically.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='members.ministryrole'),
        ),
        migrations.RunPython(choose_usher_role, migrations.RunPython.noop),
    ]
