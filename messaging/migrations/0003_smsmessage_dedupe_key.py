from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('messaging', '0002_attendance_sms_templates'),
    ]

    operations = [
        migrations.AddField(
            model_name='smsmessage',
            name='dedupe_key',
            field=models.CharField(blank=True, max_length=150, null=True, unique=True),
        ),
    ]
