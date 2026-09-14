from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_user_scope_branch_user_scope_region_user_scope_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='theme_preference',
            field=models.CharField(
                choices=[('system', 'Match device'), ('light', 'Light'), ('dark', 'Dark')],
                default='system',
                help_text='Dashboard appearance for this person.',
                max_length=10,
            ),
        ),
    ]
