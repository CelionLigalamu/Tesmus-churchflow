import uuid

from django.apps import apps
from django.db import models
from django.db.models import Q
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
    # Optional wording and photo for the public self-registration page. When
    # left blank the page uses a general welcome and the church colours.
    registration_heading = models.CharField(
        max_length=80,
        blank=True,
        help_text='Large heading beside the registration form, for example "Building Lives, Changing Nations". '
                  'Leave blank to show "Welcome to" and the church name.',
    )
    registration_message = models.CharField(
        max_length=240,
        blank=True,
        help_text='Short welcome message under the heading. Leave blank for a general welcome.',
    )
    registration_image = models.ImageField(
        upload_to='church_registration/',
        blank=True,
        null=True,
        help_text='Optional wide photo for the registration page. Without one, the church colours are used.',
    )
    # Members holding this ministry role are texted their own region's
    # statistics, alongside any pastors picked for a region by hand.
    region_pastor_role = models.ForeignKey(
        'members.MinistryRole',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='+',
        help_text="Members with this ministry role receive their own region's attendance statistics by SMS.",
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
    """An area where members live, for example Sikhendu or Msharage."""

    church = models.ForeignKey(Church, on_delete=models.CASCADE, related_name='regions')
    name = models.CharField(max_length=255)
    # Pastors are ordinary members, so they need no login: they are reached on
    # the phone number already on their member record.
    pastors = models.ManyToManyField(
        'members.Member',
        blank=True,
        related_name='pastor_of_regions',
        help_text="Members who receive this region's attendance statistics by SMS after each service.",
    )

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

    def pastor_members(self):
        """Everyone texted this region's statistics, each listed once.

        That is the pastors picked for this region, plus members who live
        here and hold the ministry role the church chose for pastors.
        """
        Member = apps.get_model('members', 'Member')
        who = Q(pastor_of_regions=self)
        if self.church.region_pastor_role_id:
            who |= Q(region=self, ministry_roles=self.church.region_pastor_role_id)
        return Member.objects.filter(church_id=self.church_id).filter(who).distinct().order_by('full_name')

    def __str__(self):
        return f"{self.church.code} - {self.name}"
