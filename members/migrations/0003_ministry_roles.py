from django.db import migrations, models
import django.db.models.deletion


DEFAULT_ROLES = (
    'Bishop',
    'Pastor',
    'Elder',
    'Deacon/Deaconess',
    'Usher',
    'Instrumentalist',
)


def create_default_roles(apps, schema_editor):
    Church = apps.get_model('tenants', 'Church')
    MinistryRole = apps.get_model('members', 'MinistryRole')
    for church in Church.objects.all():
        MinistryRole.objects.bulk_create(
            [MinistryRole(church=church, name=name) for name in DEFAULT_ROLES],
            ignore_conflicts=True,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0002_remove_member_status'),
        ('tenants', '0002_church_last_member_sequence'),
    ]

    operations = [
        migrations.CreateModel(
            name='MinistryRole',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('church', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ministry_roles', to='tenants.church')),
            ],
            options={
                'ordering': ['name'],
                'constraints': [models.UniqueConstraint(fields=('church', 'name'), name='unique_ministry_role_per_church')],
            },
        ),
        migrations.AddField(
            model_name='member',
            name='ministry_roles',
            field=models.ManyToManyField(blank=True, related_name='members', to='members.ministryrole'),
        ),
        migrations.RunPython(create_default_roles, migrations.RunPython.noop),
    ]
