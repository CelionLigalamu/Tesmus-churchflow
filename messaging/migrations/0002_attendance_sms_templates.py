from django.db import migrations


PRESENT_TEMPLATE = (
    'Mpendwa {{member_name}}, tunakushukuru kwa kushiriki nasi katika '
    '{{service_name}} ya {{service_date}}. Mungu akubariki.'
)
ABSENT_TEMPLATE = (
    'Mpendwa {{member_name}}, tulikukosa katika {{service_name}} ya '
    '{{service_date}}. Tunatumaini uko salama. Ikiwa kuna changamoto '
    'yoyote unayopitia, tafadhali wasiliana na kanisa.'
)


def create_attendance_templates(apps, schema_editor):
    Church = apps.get_model('tenants', 'Church')
    SMSTemplate = apps.get_model('messaging', 'SMSTemplate')
    defaults = {
        'attendance_present': PRESENT_TEMPLATE,
        'attendance_absent': ABSENT_TEMPLATE,
    }
    for church in Church.objects.all():
        for name, body in defaults.items():
            SMSTemplate.objects.get_or_create(
                church=church,
                name=name,
                defaults={'body': body, 'is_active': True},
            )


class Migration(migrations.Migration):
    dependencies = [
        ('messaging', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_attendance_templates, migrations.RunPython.noop),
    ]
