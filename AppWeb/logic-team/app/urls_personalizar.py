from django.urls import path

from . import views_personalizar

urlpatterns = [
    path("", views_personalizar.personalizar_perfil, name="personalizar_perfil"),
    path("modulo/", views_personalizar.personalizar_modulo, name="personalizar_modulo"),
    path("comenzar/", views_personalizar.partida_inicio, name="partida_inicio"),
]
