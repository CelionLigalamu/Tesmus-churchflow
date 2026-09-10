from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('members', '0006_order_default_ministry_roles')]

    operations = [
        migrations.AlterModelOptions(
            name='ministryrole',
            options={'ordering': ['sort_order', 'name']},
        ),
    ]
