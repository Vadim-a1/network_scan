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
class TelegramPhoto(models.Model):
    image = models.ImageField(
        upload_to="telegram_photos/%Y/%m/%d/"
    )

    telegram_id = models.BigIntegerField(
        db_index=True
    )

    telegram_username = models.CharField(
        max_length=100,
        blank=True
    )

    telegram_first_name = models.CharField(
        max_length=100,
        blank=True
    )

    caption = models.TextField(
        blank=True
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"Фото от {self.telegram_id}"