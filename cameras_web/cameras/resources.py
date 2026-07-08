from import_export import resources
from .models import Camera


class CameraResource(resources.ModelResource):
    class Meta:
        model = Camera
        import_id_fields = ("ip",)
        fields = (
            "ip",
            "name",
            "metka",
            "type",
            "model",
            "status",
            "ping",
        )