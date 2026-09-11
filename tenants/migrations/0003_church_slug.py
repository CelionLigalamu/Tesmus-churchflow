from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0002_church_last_member_sequence'),
    ]

    operations = [
        migrations.AddField(
            model_name='church',
            name='slug',
            field=models.SlugField(default='plcm', help_text='Used in the church login URL, for example plcm.', max_length=80, unique=True),
        ),
    ]
