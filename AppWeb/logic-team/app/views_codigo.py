"""CU04 — Resolver minijuego de código.

Se abre desde el menú de modos de CU05 («Minijuego de código»). Mesa de trabajo donde se arma
el algoritmo con bloques, mas la API JSON que usa js/minijuego_codigo.js. Las reglas viven en
app/services/minijuego_codigo.py y el contenido en app/data (niveles e instrucciones).
"""

import json

from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import IntentoCodigo
from .services import escenarios, minijuego_codigo, tecnicismos
from .services.minijuego_codigo import ReglaCodigo, TableroInvalido


def _cuerpo_json(request):
    try:
        datos = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return {}
    return datos if isinstance(datos, dict) else {}


def _error(mensaje, estado=400):
    return JsonResponse({"error": mensaje}, status=estado)


def _intento_del_jugador(request, intento_id, bloquear=False):
    consulta = IntentoCodigo.objects.select_for_update() if bloquear else IntentoCodigo.objects
    jugador = tecnicismos.jugador_de(request)
    return get_object_or_404(consulta.filter(**jugador.filtro()), pk=intento_id)


def _pagina_error(request, exc):
    return render(request, "partida_error.html", {"errores": exc.errores}, status=500)


# ---------------------------------------------------------------- páginas
@require_GET
def inicio(request):
    """«Minijuego de código» en el menú de modos: abre el primer nivel que falta resolver."""
    try:
        nivel_id = minijuego_codigo.nivel_para(tecnicismos.jugador_de(request))
    except escenarios.CatalogoError as exc:
        return _pagina_error(request, exc)
    return redirect("codigo_mesa", nivel_id=nivel_id)


@ensure_csrf_cookie
@require_GET
def mesa(request, nivel_id):
    """Pasos 1 a 3: la mesa de trabajo del nivel. ?nuevo=1 es «Jugar otra vez»."""
    try:
        intento = minijuego_codigo.iniciar(
            tecnicismos.jugador_de(request), nivel_id, nuevo=request.GET.get("nuevo") == "1"
        )
        estado = minijuego_codigo.estado_publico(intento)
    except ReglaCodigo as exc:
        raise Http404(str(exc)) from exc
    except escenarios.CatalogoError as exc:
        return _pagina_error(request, exc)
    return render(
        request,
        "minijuego_codigo.html",
        {"estado": estado, "nivel_id": nivel_id},
    )


# ---------------------------------------------------------------- API (js/minijuego_codigo.js)
def _accion(request, intento_id, funcion, con_tablero=True):
    try:
        with transaction.atomic():
            intento = _intento_del_jugador(request, intento_id, bloquear=True)
            argumentos = [_cuerpo_json(request)] if con_tablero else []
            resultado = funcion(intento, *argumentos)
        return JsonResponse({"codigo": resultado})
    except TableroInvalido as exc:
        return _error(str(exc), 400)
    except ReglaCodigo as exc:
        return _error(str(exc), 409)
    except escenarios.CatalogoError as exc:
        return _error("El minijuego tiene errores de contenido: " + "; ".join(exc.errores), 500)


@require_POST
def api_compilar(request, intento_id):
    """Pasos 4 y 5, FE1 y FE3. Cuerpo: {"tablero": [...], "sueltos": [...]}."""
    return _accion(request, intento_id, minijuego_codigo.compilar)


@require_POST
def api_ejecutar(request, intento_id):
    """Pasos 6 a 9 y FE2. Recibe el mismo tablero que se compiló."""
    return _accion(request, intento_id, minijuego_codigo.ejecutar)


def _salir(intento):
    minijuego_codigo.salir(intento)
    return {"url": reverse("menu_modos")}


@require_POST
def api_salir(request, intento_id):
    """FA3: abandona el intento sin XP y regresa al menú de modos."""
    return _accion(request, intento_id, _salir, con_tablero=False)
