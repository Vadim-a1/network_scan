from django.contrib import admin
from import_export.admin import ImportExportModelAdmin

from .models import Camera
from .resources import CameraResource


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