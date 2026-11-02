from django.urls import path

from . import views_codigo

# CU04: «Minijuego de código» del menú de modos (CU05)
urlpatterns = [
    path("", views_codigo.inicio, name="codigo_inicio"),
    path("<slug:nivel_id>/", views_codigo.mesa, name="codigo_mesa"),
]
