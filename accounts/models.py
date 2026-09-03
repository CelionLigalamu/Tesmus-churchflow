from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    SCOPE_CHOICES = [
        ('church', 'Church-wide'),
        ('region', 'Region'),
        ('branch', 'Branch'),
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
    scope_branch = models.ForeignKey(
        'tenants.Branch', on_delete=models.PROTECT,
        related_name='scoped_users', blank=True, null=True,
    )