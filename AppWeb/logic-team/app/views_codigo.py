"""CU04 — Resolver minijuego de código.

Se abre desde el menú de modos de CU05 («Minijuego de código»). Mesa de trabajo donde se
acomodan las líneas revueltas de un programa en Python o pseudocódigo (en cada nivel toca un
programa y una variante al azar), mas la API JSON que usa
js/minijuego_codigo.js. Las reglas viven en app/services/minijuego_codigo.py y los programas en
app/data/niveles_codigo.
"""

import json
import os

from django.contrib.staticfiles import finders
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import IntentoCodigo
from .services import escenarios, minijuego_codigo, tecnicismos
from .services.minijuego_codigo import FueraDeOrden, ProgramaInvalido, ReglaCodigo


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
    """«Minijuego de código» en el menú de modos: abre el nivel donde va la ronda.

    Si la ronda ya terminó, empieza otra. ?lenguaje=python|pseudocodigo elige el lenguaje;
    si no, se usa el último que jugó.
    """
    try:
        lenguaje, numero = minijuego_codigo.empezar(
            tecnicismos.jugador_de(request), request.GET.get("lenguaje")
        )
    except escenarios.CatalogoError as exc:
        return _pagina_error(request, exc)
    return redirect("codigo_mesa", lenguaje=lenguaje, numero=numero)


ARCHIVOS_MESA = ("js/minijuego_codigo.js", "css/minijuego_codigo.css")


def _version_archivos():
    """Cambia cada vez que se modifica el JS o el CSS de la mesa (?v= en la plantilla).

    Así el navegador no se queda con una copia vieja guardada en caché.
    """
    rutas = [finders.find(archivo) for archivo in ARCHIVOS_MESA]
    return max((int(os.path.getmtime(r)) for r in rutas if r), default=0)


def _enlaces(estado):
    """Agrega al estado las direcciones de los niveles, de otra ronda y del otro lenguaje."""
    lenguaje = estado["nivel"]["lenguaje"]
    inicio_ = reverse("codigo_inicio")
    estado["urls"] = {
        "niveles": {
            n["numero"]: reverse("codigo_mesa", args=[lenguaje, n["numero"]])
            for n in estado["ronda"]["niveles"]
        },
        "otra_ronda": f"{inicio_}?lenguaje={lenguaje}",
    }
    for leng in estado["lenguajes"]:
        leng["url"] = f"{inicio_}?lenguaje={leng['id']}"
    return estado


@ensure_csrf_cookie
@require_GET
def mesa(request, lenguaje, numero):
    """Pasos 1 a 3: la mesa de trabajo del nivel. Los niveles van en orden y no se saltan."""
    jugador = tecnicismos.jugador_de(request)
    try:
        intento = minijuego_codigo.iniciar(jugador, lenguaje, numero)
        estado = _enlaces(minijuego_codigo.estado_publico(intento))
    except FueraDeOrden as exc:
        return redirect("codigo_mesa", lenguaje=lenguaje, numero=exc.numero)
    except ReglaCodigo as exc:
        raise Http404(str(exc)) from exc
    except escenarios.CatalogoError as exc:
        return _pagina_error(request, exc)
    return render(
        request,
        "minijuego_codigo.html",
        {"estado": estado, "version": _version_archivos()},
    )


# ---------------------------------------------------------------- API (js/minijuego_codigo.js)
def _accion(request, intento_id, funcion, con_programa=True):
    try:
        with transaction.atomic():
            intento = _intento_del_jugador(request, intento_id, bloquear=True)
            argumentos = [_cuerpo_json(request)] if con_programa else []
            resultado = funcion(intento, *argumentos)
        return JsonResponse({"codigo": resultado})
    except ProgramaInvalido as exc:
        return _error(str(exc), 400)
    except ReglaCodigo as exc:
        return _error(str(exc), 409)
    except escenarios.CatalogoError as exc:
        return _error("El minijuego tiene errores de contenido: " + "; ".join(exc.errores), 500)


@require_POST
def api_comprobar(request, intento_id):
    """Pasos 4 a 9, FE1 a FE3. Cuerpo: {"programa": [{"id": "l1", "sangria": 0}, ...]}."""
    return _accion(request, intento_id, minijuego_codigo.comprobar)


def _salir(intento):
    minijuego_codigo.salir(intento)
    return {"url": reverse("menu_modos")}


@require_POST
def api_salir(request, intento_id):
    """FA3: abandona el intento sin XP y regresa al menú de modos."""
    return _accion(request, intento_id, _salir, con_programa=False)
