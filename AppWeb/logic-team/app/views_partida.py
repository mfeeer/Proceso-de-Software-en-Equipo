"""CU01 — Realizar Partida.

Pantalla del libro donde se juega la partida que creó CU02, mas una pequena API JSON que usa
js/partida.js. Las reglas del juego viven en app/services/motor_partida.py y el contenido
(escenarios, opciones, configuracion) en app/data/*.json.
"""

import json

from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import Partida
from .services import escenarios, motor_partida
from .services.motor_partida import ReglaError


def _partida_del_usuario(request, partida_id, bloquear=False):
    consulta = Partida.objects.select_for_update() if bloquear else Partida.objects
    partida = get_object_or_404(consulta, pk=partida_id)
    if partida.usuario_id and partida.usuario_id != request.user.id:
        raise Http404("Partida no encontrada")
    return partida


def _cuerpo_json(request):
    try:
        datos = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return {}
    return datos if isinstance(datos, dict) else {}


def _error(mensaje, estado=400):
    return JsonResponse({"error": mensaje}, status=estado)


def _error_catalogo(exc):
    return _error("Los escenarios tienen errores: " + "; ".join(exc.errores), 500)


# ---------------------------------------------------------------- paginas
@ensure_csrf_cookie
@require_GET
def partida_libro(request, partida_id):
    """El libro de la partida. Flujo normal pasos 1-6, FA1, FA2 y FE1."""
    partida = _partida_del_usuario(request, partida_id)
    if partida.estado != Partida.EN_CURSO and partida.resultado_pendiente is None:
        return redirect("partida_fin", partida_id=partida.id)
    try:
        estado = motor_partida.estado_publico(partida)
    except escenarios.CatalogoError as exc:
        return render(request, "partida_error.html", {"errores": exc.errores}, status=500)
    return render(request, "partida.html", {"partida_id": partida.id, "estado": estado})


@require_GET
def partida_fin(request, partida_id):
    """Pantalla Post Game: puntuacion, porcentaje de aciertos, logros y mapa de decisiones."""
    partida = _partida_del_usuario(request, partida_id)
    if partida.estado == Partida.EN_CURSO or partida.resultado_pendiente is not None:
        return redirect("partida_libro", partida_id=partida.id)
    return render(request, "post_game.html", {"resumen": motor_partida.resumen_final(partida)})


# ---------------------------------------------------------------- API (js/partida.js)
@require_GET
def api_estado(request, partida_id):
    partida = _partida_del_usuario(request, partida_id)
    try:
        return JsonResponse(motor_partida.estado_publico(partida))
    except escenarios.CatalogoError as exc:
        return _error_catalogo(exc)


def _accion(request, partida_id, funcion, *args):
    try:
        with transaction.atomic():
            partida = _partida_del_usuario(request, partida_id, bloquear=True)
            funcion(partida, *args)
        return JsonResponse(motor_partida.estado_publico(partida))
    except ReglaError as exc:
        return _error(str(exc), 409)
    except escenarios.CatalogoError as exc:
        return _error_catalogo(exc)


@require_POST
def api_decision(request, partida_id):
    opcion_id = str(_cuerpo_json(request).get("opcion_id", ""))
    return _accion(request, partida_id, motor_partida.resolver_decision, opcion_id)


@require_POST
def api_continuar(request, partida_id):
    return _accion(request, partida_id, motor_partida.continuar)


@require_POST
def api_mejorar(request, partida_id):
    atributo = str(_cuerpo_json(request).get("atributo", ""))
    return _accion(request, partida_id, motor_partida.mejorar_atributo, atributo)
