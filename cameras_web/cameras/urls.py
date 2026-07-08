from django.urls import path
from . import views


urlpatterns = [
    path("", views.camera_list, name="camera_list"),
]