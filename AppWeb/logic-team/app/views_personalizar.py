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

# Cada subtema es una tarjetita marcable: se le da un id estable ("modulo:posicion").
for _m in MODULOS:
    _m["subtemas"] = [
        {"id": f"{_m['id']}:{i}", "titulo": t} for i, t in enumerate(_m["subtemas"])
    ]

_IDS_VALIDOS = {p["id"] for p in PERFILES}
TEMAS = {t["id"]: t["titulo"] for m in MODULOS for t in m["subtemas"]}
MIN_TEMAS, MAX_TEMAS = 1, 3  # RN02: al menos 1 y como máximo 3 temas


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
    marcados = [t for t in request.session.get("temas_ids", []) if t in TEMAS]

    if request.method == "POST":
        # sin repetidos, en el orden recibido
        marcados = list(dict.fromkeys(request.POST.getlist("tema")))
        if not marcados or any(t not in TEMAS for t in marcados):
            # RN02: toda partida necesita al menos un tema educativo
            error = "Debes seleccionar al menos un tema para continuar."
            marcados = [t for t in marcados if t in TEMAS]
        elif len({t.split(":")[0] for t in marcados}) > 1:
            error = "Los temas deben ser de una sola materia."
        elif len(marcados) > MAX_TEMAS:
            error = f"Puedes elegir máximo {MAX_TEMAS} temas."
        else:
            request.session["temas_ids"] = marcados
            # TEMPORAL: aquí se creará y guardará la Partida (perfil, vidas, xp, temas).
            request.session["partida"] = {
                "perfil_id": perfil["id"],
                "vidas": perfil["vidas"],
                "xp": perfil["xp"],
                "temas": marcados,
            }
            return redirect("partida_inicio")

    return render(
        request,
        "personalizar_modulo.html",
        {
            "perfil": perfil,
            "modulos": MODULOS,
            "marcados": marcados,
            "max_temas": MAX_TEMAS,
            "error": error,
        },
    )


def partida_inicio(request):
    """TEMPORAL hasta construir la pantalla de juego (CU01): solo muestra lo que se guardó."""
    partida = request.session.get("partida")
    if not partida:
        return redirect("personalizar_perfil")
    titulos = [TEMAS[t] for t in partida["temas"] if t in TEMAS]
    return HttpResponse(
        "Partida creada (pantalla de juego pendiente). "
        f"Perfil: {partida['perfil_id']} | vidas: {partida['vidas']} | xp: {partida['xp']} | "
        f"temas: {', '.join(titulos)}"
    )
