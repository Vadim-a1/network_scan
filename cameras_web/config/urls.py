from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from cameras.views import home, photo_gallery

urlpatterns = [
    path("", home, name="home"),
    path("photos/", photo_gallery, name="photo_gallery"),
    path("admin/", admin.site.urls),
    path("cameras/", include("cameras.urls")),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )