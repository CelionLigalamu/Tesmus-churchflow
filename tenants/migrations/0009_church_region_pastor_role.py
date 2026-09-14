import django.db.models.deletion
from django.db import migrations, models


def choose_pastor_role(apps, schema_editor):
    """Existing churches start with their own "Pastor" ministry role, when they have one."""
    Church = apps.get_model('tenants', 'Church')
    MinistryRole = apps.get_model('members', 'MinistryRole')
    for church in Church.objects.filter(region_pastor_role__isnull=True):
        role = MinistryRole.objects.filter(church=church, name__iexact='pastor').first()
        if role:
            church.region_pastor_role = role
            church.save(update_fields=['region_pastor_role'])


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0008_remove_member_branch'),
        ('tenants', '0008_delete_branch'),
    ]

    operations = [
        migrations.AddField(
            model_name='church',
            name='region_pastor_role',
            field=models.ForeignKey(blank=True, help_text="Members with this ministry role receive their own region's attendance statistics by SMS.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='members.ministryrole'),
        ),
        migrations.RunPython(choose_pastor_role, migrations.RunPython.noop),
    ]
