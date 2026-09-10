from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('messaging', '0003_smsmessage_dedupe_key')]

    operations = [
        migrations.AddField(
            model_name='smsmessage',
            name='audience_type',
            field=models.CharField(choices=[('church', 'All members'), ('leadership', 'Leadership group'), ('region', 'Members in a region'), ('branch', 'Members in a branch'), ('service_present', 'Members present at a service'), ('service_absent', 'Members absent from a service'), ('visitor_present', 'Visitors present at a service'), ('individual', 'Individual or automated message')], default='individual', max_length=30),
        ),
        migrations.AddField(
            model_name='smsmessage',
            name='audience_label',
            field=models.CharField(blank=True, max_length=150),
        ),
    ]
