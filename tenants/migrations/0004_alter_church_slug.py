from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0003_church_slug'),
    ]

    operations = [
        migrations.AlterField(
            model_name='church',
            name='slug',
            field=models.SlugField(blank=True, help_text='Used in the church login URL, for example plcm.', max_length=80, unique=True),
        ),
    ]
