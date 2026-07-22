from django.urls import path
from . import views
from .views import photo_gallery


urlpatterns = [
    path("", views.camera_list, name="camera_list"),
    
]