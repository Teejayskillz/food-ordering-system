from django.conf import settings
from django.db import models

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField(max_length=30, blank=True)
    default_address = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"Profile: {self.user}"
