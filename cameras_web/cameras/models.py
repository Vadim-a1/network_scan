from django.db import models


class Camera(models.Model):
    ip = models.GenericIPAddressField(unique=True)
    name = models.CharField(max_length=100)
    metka = models.CharField(max_length=100, blank=True)
    type = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=100, blank=True)
    ping = models.CharField(max_length=100, blank=True)
    last_check = models.DateTimeField(blank=True, null=True)
    last_OK = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.name