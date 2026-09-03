from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    is_tesmus_staff = models.BooleanField(
        default=False,
        help_text="True for Tesmus Technologies platform staff, not church users."
    )