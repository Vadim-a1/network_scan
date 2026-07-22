from django.contrib import admin
from import_export.admin import ImportExportModelAdmin

from .models import Camera
from .resources import CameraResource

from .models import TelegramPhoto


@admin.register(Camera)
class CameraAdmin(ImportExportModelAdmin):
    resource_class = CameraResource

    list_display = (
    "name",
    "ip",
    "metka",
    "type",
    "model",
    "status",
    "ping",
)

search_fields = (
    "name",
    "ip",
    "model",
    "metka",
)

list_filter = (
    "status",
    "metka",
    "type",
)

@admin.register(TelegramPhoto)
class TelegramPhotoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "telegram_id",
        "telegram_username",
        "telegram_first_name",
        "caption",
        "uploaded_at",
    )
    search_fields = (
        "telegram_id",
        "telegram_username",
        "telegram_first_name",
        "caption",
    )
    list_filter = (
        "uploaded_at",
    )