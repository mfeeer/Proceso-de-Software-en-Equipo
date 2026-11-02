from django.urls import path

from . import views, views_cuestionario

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
]
