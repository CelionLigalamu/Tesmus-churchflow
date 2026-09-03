from django.db import models


class Church(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, unique=True)
    logo = models.ImageField(upload_to='church_logos/', blank=True, null=True)
    primary_color = models.CharField(max_length=7, default='#0d6efd')
    secondary_color = models.CharField(max_length=7, default='#6c757d')
    accent_color = models.CharField(max_length=7, default='#198754')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Region(models.Model):
    church = models.ForeignKey(Church, on_delete=models.CASCADE, related_name='regions')
    name = models.CharField(max_length=255)

    class Meta:
        unique_together = ('church', 'name')

    def __str__(self):
        return f"{self.church.code} - {self.name}"


class Branch(models.Model):
    church = models.ForeignKey(Church, on_delete=models.CASCADE, related_name='branches')
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='branches', blank=True, null=True)
    name = models.CharField(max_length=255)

    class Meta:
        unique_together = ('church', 'name')

    def __str__(self):
        return f"{self.church.code} - {self.name}"
