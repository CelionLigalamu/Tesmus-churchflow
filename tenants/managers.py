from django.db import models


class TenantManager(models.Manager):
    def for_user(self, user):
        if user.is_tesmus_staff:
            return self.all()
        if user.church_id is None:
            return self.none()
        return self.filter(church_id=user.church_id)