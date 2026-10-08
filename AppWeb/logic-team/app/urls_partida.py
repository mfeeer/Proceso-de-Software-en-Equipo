from django.urls import path

from . import views_partida

urlpatterns = [
    path("<uuid:partida_id>/", views_partida.partida_libro, name="partida_libro"),
    path("<uuid:partida_id>/fin/", views_partida.partida_fin, name="partida_fin"),
    # API que usa js/partida.js
    path("<uuid:partida_id>/estado/", views_partida.api_estado, name="partida_api_estado"),
    path("<uuid:partida_id>/decision/", views_partida.api_decision, name="partida_api_decision"),
    path("<uuid:partida_id>/continuar/", views_partida.api_continuar, name="partida_api_continuar"),
    path("<uuid:partida_id>/mejorar/", views_partida.api_mejorar, name="partida_api_mejorar"),
]
