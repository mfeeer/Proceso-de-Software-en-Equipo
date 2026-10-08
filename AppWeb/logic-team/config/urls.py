from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("app.urls")),
    path("personalizar/", include("app.urls_personalizar")),
       path("personalizar-partida/", RedirectView.as_view(pattern_name="personalizar_perfil")),
    path("", TemplateView.as_view(template_name="index.html"), name="home"),
]
