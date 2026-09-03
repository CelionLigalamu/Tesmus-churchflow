from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    is_tesmus_staff = models.BooleanField(default=False)
    church = models.ForeignKey(
        'tenants.Church',
        on_delete=models.PROTECT,
        related_name='users',
        blank=True,
        null=True,
    )