from django.db import migrations, models


DEFAULT_ROLES = (
    'Bishop',
    'Pastor',
    'Elder',
    'Deacon',
    'Deaconess',
    'Ushers',
    'Instrumentalists',
)


def normalize_roles(apps, schema_editor):
    MinistryRole = apps.get_model('members', 'MinistryRole')
    for church_id in MinistryRole.objects.values_list('church_id', flat=True).distinct():
        roles = {role.name: role for role in MinistryRole.objects.filter(church_id=church_id)}
        legacy_pairs = {
            'Deacon/Deaconess': 'Deaconess',
            'Usher': 'Ushers',
            'Instrumentalist': 'Instrumentalists',
        }
        for old_name, new_name in legacy_pairs.items():
            old_role = roles.get(old_name)
            if not old_role:
                continue
            target = roles.get(new_name)
            if target:
                for member in old_role.members.all():
                    member.ministry_roles.add(target)
                old_role.delete()
            else:
                old_role.name = new_name
                old_role.save(update_fields=['name'])
                roles[new_name] = old_role
        for index, name in enumerate(DEFAULT_ROLES, start=1):
            role = MinistryRole.objects.filter(church_id=church_id, name=name).first()
            if role:
                role.sort_order = index * 10
                role.save(update_fields=['sort_order'])
        MinistryRole.objects.filter(church_id=church_id).exclude(name__in=DEFAULT_ROLES).update(sort_order=1000)


class Migration(migrations.Migration):
    dependencies = [('members', '0005_remove_member_status')]

    operations = [
        migrations.AddField(
            model_name='ministryrole',
            name='sort_order',
            field=models.PositiveIntegerField(default=1000),
        ),
        migrations.RunPython(normalize_roles, migrations.RunPython.noop),
    ]
