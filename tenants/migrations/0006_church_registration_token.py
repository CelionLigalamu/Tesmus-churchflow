"""Add the public self-registration token to Church.

Written by hand rather than auto-generated: adding a unique field to a table
that already has rows needs three steps, otherwise every existing church would
be given the same token.
"""
import uuid

from django.db import migrations, models


def fill_tokens(apps, schema_editor):
    Church = apps.get_model('tenants', 'Church')
    for church in Church.objects.filter(registration_token__isnull=True):
        church.registration_token = uuid.uuid4()
        church.save(update_fields=['registration_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0005_alter_branch_options_alter_region_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='church',
            name='self_registration_enabled',
            field=models.BooleanField(
                default=True,
                help_text='Allow people to register themselves using the church link.',
            ),
        ),
        # 1. add it nullable and non-unique so existing rows are accepted
        migrations.AddField(
            model_name='church',
            name='registration_token',
            field=models.UUIDField(null=True, editable=False),
        ),
        # 2. give every existing church its own token
        migrations.RunPython(fill_tokens, migrations.RunPython.noop),
        # 3. now the uniqueness constraint can be applied safely
        migrations.AlterField(
            model_name='church',
            name='registration_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
