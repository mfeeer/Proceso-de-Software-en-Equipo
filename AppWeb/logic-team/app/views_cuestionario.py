"""CU05 — Completar cuestionario de tecnicismos.

Menú de modos de juego (RF-51), pantalla del cuestionario y la API JSON que usa
js/cuestionario.js. Las reglas viven en app/services/cuestionario.py y el catálogo en
app/data/tecnicismos.json.
"""

import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .services import cuestionario, escenarios, minijuego_codigo, tecnicismos


def _cuerpo_json(request):
    try:
        datos = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return {}
    return datos if isinstance(datos, dict) else {}


def _error(error, estado=400, **extra):
    return JsonResponse({"error": error, **extra}, status=estado)


def _error_catalogo(exc):
    return _error("El catálogo de tecnicismos tiene errores: " + "; ".join(exc.errores), 500)


# ---------------------------------------------------------------- páginas
@ensure_csrf_cookie
@require_GET
def menu_modos(request):
    """Pasos 1 y 2: «Iniciar juego» muestra «Historia narrativa», «Minijuego de código» (CU04)
    y «Cuestionario súbito»."""
    jugador = tecnicismos.jugador_de(request)
    try:
        resumen = cuestionario.resumen_jugador(jugador)
        codigo = minijuego_codigo.resumen_jugador(jugador)
    except escenarios.CatalogoError as exc:
        return render(request, "partida_error.html", {"errores": exc.errores}, status=500)
    return render(request, "modos.html", {"resumen": resumen, "codigo": codigo})


@ensure_csrf_cookie
@require_GET
def pagina_cuestionario(request):
    """Pasos 7 a 13. js/cuestionario.js pide el cuestionario y dibuja la mesa de trabajo."""
    return render(request, "cuestionario.html")


# ---------------------------------------------------------------- API (js/cuestionario.js)
@require_POST
def api_generar(request):
    """Pasos 4 a 6 (y FA4: cada llamada arma un cuestionario nuevo). FA1 responde 409."""
    try:
        return JsonResponse(cuestionario.crear(tecnicismos.jugador_de(request)))
    except cuestionario.Insuficientes as exc:
        return _error(
            "insuficientes",
            409,
            registrados=exc.registrados,
            necesarios=exc.necesarios,
            mensaje=str(exc),
        )
    except escenarios.CatalogoError as exc:
        return _error_catalogo(exc)


@require_POST
def api_resultado(request):
    """Pasos 10 y 11, y FE1 (sincronizar un resultado pendiente).

    Cuerpo: {"token": "...", "respuestas": [1, 0, 3, ...], "fecha": "ISO-8601",
             "pendiente": false}
    201 si se guardó; 200 si ese cuestionario ya estaba guardado (reintento).
    """
    datos = _cuerpo_json(request)
    try:
        resultado, creado = cuestionario.guardar_resultado(
            tecnicismos.jugador_de(request),
            datos.get("token"),
            datos.get("respuestas"),
            fecha=datos.get("fecha"),
            pendiente=bool(datos.get("pendiente")),
        )
    except cuestionario.CuestionarioAjeno as exc:
        return _error(str(exc), 403)
    except cuestionario.ResultadoInvalido as exc:
        return _error(str(exc), 400)
    except escenarios.CatalogoError as exc:
        return _error_catalogo(exc)
    return JsonResponse(resultado, status=201 if creado else 200)
