from django.db import migrations, models


def move_open_future_services_to_upcoming(apps, schema_editor):
    Service = apps.get_model('services', 'Service')
    Service.objects.filter(status='open').update(status='upcoming')


class Migration(migrations.Migration):
    dependencies = [
        ('services', '0002_service_qr_token'),
    ]

    operations = [
        migrations.AlterField(
            model_name='service',
            name='status',
            field=models.CharField(
                choices=[
                    ('upcoming', 'Upcoming'),
                    ('open', 'Open'),
                    ('closed', 'Closed'),
                    ('finalized', 'Finalized'),
                ],
                default='upcoming',
                max_length=10,
            ),
        ),
        migrations.RunPython(move_open_future_services_to_upcoming, migrations.RunPython.noop),
    ]
