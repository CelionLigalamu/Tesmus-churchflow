from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('members', '0004_restore_member_status')]

    operations = [
        migrations.RemoveField(model_name='member', name='status'),
    ]
