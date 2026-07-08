from django.shortcuts import render

# Create your views here.
from django.shortcuts import render
from .models import Camera


def camera_list(request):
    cameras = Camera.objects.all()
    camera_query = Camera.objects.all().order_by("name")
    total_count = camera_query.count()
    online_count = camera_query.filter(status="online").count()
    offline_count = total_count - online_count

    return render(
        request,
        "cameras/list.html",
        {
            "cameras": cameras,
            "total_count": total_count,
            "online_count": online_count,
            "offline_count": offline_count,
        }
    )