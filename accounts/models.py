from django.conf import settings
from django.db import models

# accounts/models.py

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    phone = models.CharField(max_length=30, blank=True)
    default_address = models.TextField(blank=True)

    is_delivery_guy = models.BooleanField(default=False)
    def __str__(self) -> str:
        return f"Profile: {self.user}"

