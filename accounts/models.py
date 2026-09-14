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
    # Ushers are kept to the usher check-in screen by accounts.middleware.
    is_usher = models.BooleanField(
        default=False,
        help_text='Can only use the usher check-in screen for their church, and nothing else.',
    )
    # The member record of the person who uses this sign-in (for ushers).
    member = models.OneToOneField(
        'members.Member',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='user_account',
        help_text='The member record of the person who uses this sign-in.',
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
