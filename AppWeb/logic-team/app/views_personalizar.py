"""CU02 — Personalizar Partida.

Pantalla 1: elegir perfil / antecedente.
Pantalla 2: elegir módulos temáticos y confirmar con "Comenzar Aventura".

Los perfiles y módulos están definidos aquí mientras no existan los modelos (app/models.py
aún está vacío). Cuando existan Perfil y Tema, estas listas se reemplazan por consultas.
OJO: vidas y xp de los perfiles son valores de ejemplo; hay que confirmarlos con el equipo.
"""
from django.http import HttpResponse
from django.shortcuts import redirect, render

PERFILES = [
    {
        "id": "recien-egresado",
        "clase": "RecienEgresado",
        "titulo": "Recién egresado de prepa",
        "descripcion": "17 años, conocimiento nulo en programación. Empieza desde cero, con mucha curiosidad y poca base técnica.",
        "teoria": "baja", "equipo": "media", "inteligencia": "media",
        "vidas": 3, "xp": 0,
    },
    {
        "id": "carrera-afin",
        "clase": "CarreraAfín",
        "titulo": "Carrera afín, sin software",
        "descripcion": "Viene de una ingeniería relacionada (mecatrónica, industrial). Tiene bases de lógica pero no de programación.",
        "teoria": "media", "equipo": "media", "inteligencia": "alta",
        "vidas": 3, "xp": 20,
    },
    {
        "id": "segunda-carrera",
        "clase": "SegundaCarrera",
        "titulo": "Segunda carrera, área distinta",
        "descripcion": "Cambia de carrera desde un área no relacionada. Trae disciplina y perspectiva, pero arranca casi de cero en lo técnico.",
        "teoria": "baja", "equipo": "alta", "inteligencia": "media",
        "vidas": 3, "xp": 10,
    },
    {
        "id": "abierto",
        "clase": "Abierto",
        "titulo": "Antecedente abierto",
        "descripcion": "Sin historia predefinida: atributos equilibrados para quien prefiere descubrir su camino sobre la marcha.",
        "teoria": "media", "equipo": "media", "inteligencia": "media",
        "vidas": 3, "xp": 10,
    },
]

# Módulos temáticos de Ingeniería de Software. Las descripciones son textos de ejemplo.
MODULOS = [
    {
        "id": "intro-programacion",
        "clase": "IntroProgramacion",
        "titulo": "Introducción a la programación",
        "descripcion": "Los cimientos del código: cómo se guardan los datos y cómo un programa decide qué hacer.",
        "subtemas": ["Tipos de datos y variables", "Estructuras de control"],
    },
    {
        "id": "logica-algoritmos",
        "clase": "LogicaAlgoritmos",
        "titulo": "Lógica y algoritmos",
        "descripcion": "Pensar paso a paso: representar un algoritmo y elegir cómo buscar y ordenar información.",
        "subtemas": ["Representación de algoritmos", "Algoritmos de búsqueda y ordenamiento"],
    },
    {
        "id": "programacion-oo",
        "clase": "ProgramacionOO",
        "titulo": "Programación orientada a objetos",
        "descripcion": "Modelar el mundo con clases y objetos, y saber qué hacer cuando algo sale mal.",
        "subtemas": ["Clases y objetos", "Manejo de excepciones"],
    },
    {
        "id": "ingenieria-requerimientos",
        "clase": "IngenieriaRequerimientos",
        "titulo": "Ingeniería de requerimientos",
        "descripcion": "Antes de programar hay que entender qué se necesita: clasificarlo, especificarlo y validarlo.",
        "subtemas": [
            "Fundamentos y clasificación de requerimientos",
            "Ciclo de vida de requerimientos",
            "Especificación de requerimientos",
            "Validación y verificación de requerimientos",
        ],
    },
]

_IDS_VALIDOS = {p["id"] for p in PERFILES}
_IDS_MODULOS = {m["id"] for m in MODULOS}


def _perfil_de_sesion(request):
    pid = request.session.get("perfil_id")
    return next((p for p in PERFILES if p["id"] == pid), None)


def personalizar_perfil(request):
    """Pantalla 1/2. Flujo normal pasos 2-3; FE1 y RN03 si no se elige perfil."""
    error = None

    if request.method == "POST":
        elegido = request.POST.get("perfil")
        if elegido in _IDS_VALIDOS:
            request.session["perfil_id"] = elegido
            return redirect("personalizar_modulo")
        # FE1 / RN03: no se avanza sin un perfil válido
        error = "Debes seleccionar un perfil para continuar."

    return render(
        request,
        "personalizar_perfil.html",
        {
            "perfiles": PERFILES,
            "perfil_actual": request.session.get("perfil_id"),
            "error": error,
        },
    )


def personalizar_modulo(request):
    """Pantalla 2/2. Flujo normal pasos 4-6; RN02: al menos un tema educativo obligatorio."""
    perfil = _perfil_de_sesion(request)
    if perfil is None:
        # RN03: sin perfil inicial no se puede personalizar el resto de la partida
        return redirect("personalizar_perfil")

    error = None

    if request.method == "POST":
        elegido = request.POST.get("modulo")
        if elegido in _IDS_MODULOS:
            request.session["modulo_id"] = elegido
            # TEMPORAL: aquí se creará y guardará la Partida (perfil, vidas, xp, temas).
            # "temas" es una lista para poder asignar más de un tema en el futuro.
            request.session["partida"] = {
                "perfil_id": perfil["id"],
                "vidas": perfil["vidas"],
                "xp": perfil["xp"],
                "temas": [elegido],
            }
            return redirect("partida_inicio")
        # RN02: toda partida necesita al menos un tema educativo
        error = "Debes seleccionar un módulo temático para continuar."

    return render(
        request,
        "personalizar_modulo.html",
        {
            "perfil": perfil,
            "modulos": MODULOS,
            "modulo_actual": request.session.get("modulo_id"),
            "error": error,
        },
    )


def partida_inicio(request):
    """TEMPORAL hasta construir la pantalla de juego (CU01): solo muestra lo que se guardó."""
    partida = request.session.get("partida")
    if not partida:
        return redirect("personalizar_perfil")
    titulos = [m["titulo"] for m in MODULOS if m["id"] in partida["temas"]]
    return HttpResponse(
        "Partida creada (pantalla de juego pendiente). "
        f"Perfil: {partida['perfil_id']} | vidas: {partida['vidas']} | xp: {partida['xp']} | "
        f"temas: {', '.join(titulos)}"
    )
