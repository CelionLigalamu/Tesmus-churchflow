from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('members', '0003_ministry_roles')]

    operations = [
        migrations.AddField(
            model_name='member',
            name='status',
            field=models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive')], default='active', max_length=10),
        ),
    ]
