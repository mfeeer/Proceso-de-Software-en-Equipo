from django.urls import path

from . import views, views_codigo, views_cuestionario

urlpatterns = [
    path("health/", views.health, name="health"),
    # CU05 - Cuestionario de tecnicismos (API que usa js/cuestionario.js)
    path(
        "cuestionario/generar/",
        views_cuestionario.api_generar,
        name="cuestionario_generar",
    ),
    path(
        "cuestionario/resultado/",
        views_cuestionario.api_resultado,
        name="cuestionario_resultado",
    ),
    # CU04 - Minijuego de código (API que usa js/minijuego_codigo.js)
    path(
        "codigo/<uuid:intento_id>/comprobar/", views_codigo.api_comprobar, name="codigo_comprobar"
    ),
    path("codigo/<uuid:intento_id>/salir/", views_codigo.api_salir, name="codigo_salir"),
]
