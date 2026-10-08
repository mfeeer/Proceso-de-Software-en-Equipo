"""CU02 — Personalizar Partida.

Pantalla 1: elegir perfil / antecedente.
Pantalla 2: elegir módulos temáticos y confirmar con "Comenzar Aventura".

Los perfiles y módulos están definidos aquí mientras no existan los modelos (app/models.py
aún está vacío). Cuando existan Perfil y Tema, estas listas se reemplazan por consultas.
OJO: los valores de los perfiles son una propuesta equilibrada; hay que confirmarlos con el equipo.
"""
import json

from django.shortcuts import redirect, render

from .services import escenarios, motor_partida

# Atributos de 1 a 10 (los mismos del juego, ver app/data/config_juego.json).
# Equilibrio: todos los perfiles reparten 9 puntos y empiezan con 3 vidas y 0 XP;
# lo que cambia es en qué destaca cada uno y qué le cuesta.
PERFILES = [
    {
        "id": "recien-egresado",
        "clase": "RecienEgresado",
        "titulo": "Recién egresado de prepa",
        "descripcion": "17 años, conocimiento nulo en programación. Empieza desde cero, con "
        "mucha curiosidad y facilidad para hacer equipo, pero poca base técnica.",
        "teoria": 1, "equipo": 4, "inteligencia": 4,
        "vidas": 3, "xp": 0,
    },
    {
        "id": "carrera-afin",
        "clase": "CarreraAfín",
        "titulo": "Carrera afín, sin software",
        "descripcion": "Viene de una ingeniería relacionada (mecatrónica, industrial). Tiene "
        "bases de lógica pero no de programación, y le cuesta delegar.",
        "teoria": 3, "equipo": 2, "inteligencia": 4,
        "vidas": 3, "xp": 0,
    },
    {
        "id": "segunda-carrera",
        "clase": "SegundaCarrera",
        "titulo": "Segunda carrera, área distinta",
        "descripcion": "Cambia de carrera desde un área no relacionada. Trae disciplina y "
        "don de gente, pero arranca casi de cero en lo técnico.",
        "teoria": 2, "equipo": 5, "inteligencia": 2,
        "vidas": 3, "xp": 0,
    },
    {
        "id": "lobo-solitario",
        "clase": "LoboSolitario",
        "titulo": "Lobo solitario",
        "descripcion": "Aprendió por su cuenta con documentación y foros. Domina la teoría y "
        "resuelve problemas rápido, pero trabajar en equipo no es lo suyo.",
        "teoria": 4, "equipo": 1, "inteligencia": 4,
        "vidas": 3, "xp": 0,
    },
    {
        "id": "abierto",
        "clase": "Abierto",
        "titulo": "Antecedente abierto",
        "descripcion": "Sin historia predefinida: atributos equilibrados para quien prefiere "
        "descubrir su camino sobre la marcha.",
        "teoria": 3, "equipo": 3, "inteligencia": 3,
        "vidas": 3, "xp": 0,
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
MIN_TEMAS = 1  # RN02: al menos 1 tema; se pueden combinar temas de varias materias


def _perfiles_con_atributos():
    """Perfiles con sus atributos como se usan en el juego (CU01): nombre, ícono y valor.

    Los nombres, íconos y el valor máximo vienen de app/data/config_juego.json, así que
    CU02 y la partida siempre muestran lo mismo.
    """
    config, _ = escenarios.cargar()
    perfiles = []
    for p in PERFILES:
        atributos = [
            {**a, "valor": motor_partida.valor_atributo(p.get(a["id"], 0), config)}
            for a in config["atributos"]
        ]
        perfiles.append(
            {
                **p,
                "atributos": atributos,
                "atributos_json": json.dumps({a["id"]: a["valor"] for a in atributos}),
            }
        )
    maximo = config["niveles"]["maximo_atributo"]
    return perfiles, config["atributos"], maximo


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

    perfiles, atributos, maximo = _perfiles_con_atributos()
    return render(
        request,
        "personalizar_perfil.html",
        {
            "perfiles": perfiles,
            "atributos": atributos,
            "nivel_maximo": range(maximo),
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
            "max_eventos": escenarios.cargar()[0]["max_eventos_por_partida"],
            "error": error,
        },
    )


def partida_inicio(request):
    """Paso 5: crea y guarda la Partida con lo elegido y abre el libro del CU01."""
    datos = request.session.pop("partida", None)
    if not datos:
        # Refrescar esta URL vuelve a la partida recién creada en vez de crear otra.
        ultima = request.session.get("partida_actual")
        return redirect("partida_libro", partida_id=ultima) if ultima else redirect(
            "personalizar_perfil"
        )
    perfil = next((p for p in PERFILES if p["id"] == datos.get("perfil_id")), None)
    try:
        partida = motor_partida.crear_partida(
            perfil,
            datos.get("temas", []),
            usuario=request.user if request.user.is_authenticated else None,
        )
    except motor_partida.ReglaError:
        return redirect("personalizar_perfil" if perfil is None else "personalizar_modulo")
    request.session["partida_actual"] = str(partida.id)
    return redirect("partida_libro", partida_id=partida.id)
