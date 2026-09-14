from django.db import migrations


def branch_scope_to_none(apps, schema_editor):
    """Branches no longer exist; anyone limited to one keeps no scope until reassigned."""
    User = apps.get_model('accounts', 'User')
    User.objects.filter(scope_type='branch').update(scope_type='none')


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_user_theme_preference'),
    ]

    operations = [
        migrations.RunPython(branch_scope_to_none, migrations.RunPython.noop),
    ]
