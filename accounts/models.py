from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    SCOPE_CHOICES = [
        ('church', 'Church-wide'),
        ('region', 'Region'),
        ('none', 'None'),
    ]

    is_tesmus_staff = models.BooleanField(default=False)
    church = models.ForeignKey(
        'tenants.Church', on_delete=models.PROTECT,
        related_name='users', blank=True, null=True,
    )
    scope_type = models.CharField(max_length=10, choices=SCOPE_CHOICES, default='none')
    scope_region = models.ForeignKey(
        'tenants.Region', on_delete=models.PROTECT,
        related_name='scoped_users', blank=True, null=True,
    )

    THEME_CHOICES = [
        ('system', 'Match device'),
        ('light', 'Light'),
        ('dark', 'Dark'),
    ]
    theme_preference = models.CharField(
        max_length=10,
        choices=THEME_CHOICES,
        default='system',
        help_text='Dashboard appearance for this person.',
    )
