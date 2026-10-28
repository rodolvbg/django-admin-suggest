from django.urls import path
from gallery.admin_unfold import site

urlpatterns = [
    path("admin/", site.urls),
]
