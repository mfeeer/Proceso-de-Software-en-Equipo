from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("app.urls")),
    path("personalizar/", include("app.urls_personalizar")),
    path("", TemplateView.as_view(template_name="index.html"), name="home"),
]
