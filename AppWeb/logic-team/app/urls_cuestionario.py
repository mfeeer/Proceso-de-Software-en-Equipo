from django.urls import path

from . import views_cuestionario

# CU05: «Iniciar juego» abre el menú de modos (RF-51)
urlpatterns = [
    path("", views_cuestionario.menu_modos, name="menu_modos"),
    path("cuestionario/", views_cuestionario.pagina_cuestionario, name="cuestionario"),
]
