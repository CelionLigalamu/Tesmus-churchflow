import uuid

from django.db import models
from django.db.models.functions import Lower
from django.utils.text import slugify


class Church(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, unique=True)
    slug = models.SlugField(max_length=80, unique=True, blank=True, help_text='Used in the church login URL, for example plcm.')
    logo = models.ImageField(upload_to='church_logos/', blank=True, null=True)
    primary_color = models.CharField(max_length=7, default='#0d6efd')
    secondary_color = models.CharField(max_length=7, default='#6c757d')
    accent_color = models.CharField(max_length=7, default='#198754')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_member_sequence = models.PositiveIntegerField(default=0)
    # Unguessable token for the church's public self-registration link, the
    # same approach already used for service QR check-in.
    registration_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    self_registration_enabled = models.BooleanField(
        default=True,
        help_text='Allow people to register themselves using the church link.',
    )

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.code or self.name) or 'church'
            candidate = base_slug
            suffix = 2
            while type(self).objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f'{base_slug}-{suffix}'
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Region(models.Model):
    church = models.ForeignKey(Church, on_delete=models.CASCADE, related_name='regions')
    name = models.CharField(max_length=255)

    class Meta:
        # Case-insensitive so "Kasarani" and "kasarani" cannot both exist.
        # Enforced in the database, not just in the form, because imports and
        # the admin write here too.
        constraints = [
            models.UniqueConstraint(
                Lower('name'), 'church', name='unique_region_name_per_church'
            ),
        ]
        ordering = ['name']

    def __str__(self):
        return f"{self.church.code} - {self.name}"


class Branch(models.Model):
    church = models.ForeignKey(Church, on_delete=models.CASCADE, related_name='branches')
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='branches', blank=True, null=True)
    name = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower('name'), 'church', name='unique_branch_name_per_church'
            ),
        ]
        ordering = ['name']

    def __str__(self):
        return f"{self.church.code} - {self.name}"
