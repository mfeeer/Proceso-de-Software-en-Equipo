"""Carga y validacion de los escenarios y de la configuracion del juego (CU-01).

El contenido vive en app/data/*.json, separado del codigo web (RNF-MAN-05), para poder
editarlo y validarlo de forma aislada. Los archivos se vuelven a leer solos cuando cambian,
asi que basta con editar el JSON y refrescar el navegador.
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ESCENARIOS_DIR = DATA_DIR / "escenarios"
CONFIG_PATH = DATA_DIR / "config_juego.json"

NORMAL = "normal"
PROBABILIDAD = "probabilidad"
CLAVES_EVENTOS = {NORMAL: "eventos_normales", PROBABILIDAD: "eventos_probabilidad"}
CONDICIONES_LOGRO = {"completar", "sin_dano", "precision_minima", "exitos_riesgosos"}
MIN_OPCIONES, MAX_OPCIONES = 2, 4
CLAVES_CONFIG = (
    "max_eventos_por_partida",
    "bloques",
    "hp",
    "xp",
    "puntos",
    "probabilidad",
    "atributos",
    "niveles",
    "riesgo",
    "logros",
    "finales",
)

_cache = {"firma": None, "resultado": None}


class CatalogoError(Exception):
    """Los archivos de escenarios o de configuracion tienen errores."""

    def __init__(self, errores):
        self.errores = list(errores)
        super().__init__("; ".join(self.errores))


def _archivos():
    return [CONFIG_PATH, *sorted(ESCENARIOS_DIR.glob("*.json"))]


def _firma():
    return tuple((str(ruta), ruta.stat().st_mtime_ns) for ruta in _archivos())


def _leer(ruta, errores):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errores.append(f"{ruta.name}: JSON invalido (linea {exc.lineno}): {exc.msg}")
    except OSError as exc:
        errores.append(f"{ruta.name}: no se pudo leer ({exc})")
    return None


def _texto_ok(valor):
    return isinstance(valor, str) and valor.strip() != ""


def _validar_bloques(bloques, donde, errores):
    if not bloques:
        errores.append(f"{donde}: debe haber al menos un bloque")
        return
    anterior = 0
    for bloque in bloques:
        limite = bloque.get("hasta_porcentaje")
        if not isinstance(limite, (int, float)) or limite <= anterior:
            errores.append(f"{donde}: 'hasta_porcentaje' de los bloques debe ir en orden")
        else:
            anterior = limite
        if not 0 <= bloque.get("probabilidad_evento", -1) <= 1:
            errores.append(f"{donde}: 'probabilidad_evento' debe estar entre 0 y 1")
        for clave in ("capitulo", "nombre"):
            if not _texto_ok(bloque.get(clave)):
                errores.append(f"{donde}: cada bloque necesita '{clave}'")
    if bloques[-1].get("hasta_porcentaje") != 100:
        errores.append(f"{donde}: el ultimo bloque debe terminar en 100")


def _validar_riesgo(niveles, donde, errores):
    anterior = -1
    for nivel in niveles:
        if nivel.get("hasta", -1) <= anterior:
            errores.append(f"{donde}: 'hasta' de los niveles de riesgo debe ir en orden")
        anterior = nivel.get("hasta", -1)
        for clave in ("mensaje_exito", "mensaje_fallo"):
            if not _texto_ok(nivel.get(clave)):
                errores.append(f"{donde}: cada nivel de riesgo necesita '{clave}'")
    if not niveles or niveles[-1].get("hasta") != 100:
        errores.append(f"{donde}: el ultimo nivel de riesgo debe terminar en 100")


def _validar_config(config, errores):
    donde = CONFIG_PATH.name
    faltan = [clave for clave in CLAVES_CONFIG if clave not in config]
    for clave in faltan:
        errores.append(f"{donde}: falta la clave '{clave}'")
    if faltan:
        return

    maximo = config["max_eventos_por_partida"]
    if not isinstance(maximo, int) or maximo < 1:
        errores.append(f"{donde}: max_eventos_por_partida debe ser un entero mayor a 0")
    _validar_bloques(config["bloques"], donde, errores)

    ids = [a.get("id") for a in config["atributos"]]
    if not ids or len(set(ids)) != len(ids) or not all(_texto_ok(i) for i in ids):
        errores.append(f"{donde}: los atributos necesitan ids unicos y no vacios")
    niveles = config["niveles"]
    for clave in ("maximo_personaje", "maximo_atributo"):
        if not isinstance(niveles.get(clave), int) or niveles.get(clave) < 1:
            errores.append(f"{donde}: niveles.{clave} debe ser un entero mayor a 0")
    for clave in ("por_acierto", "por_nivel"):
        if not isinstance(config["xp"].get(clave), int) or config["xp"].get(clave) < 1:
            errores.append(f"{donde}: xp.{clave} debe ser un entero mayor a 0")

    _validar_riesgo(config["riesgo"], donde, errores)
    for logro in config["logros"]:
        if logro.get("condicion") not in CONDICIONES_LOGRO:
            errores.append(f"{donde}: logro '{logro.get('id')}' con condicion desconocida")
    _validar_finales(config["finales"], donde, errores)


def _validar_finales(finales, donde, errores):
    """Un final de partida completada y varios de derrota, uno por tramo de eventos."""
    completada = finales.get("completada", {})
    if not _texto_ok(completada.get("titulo")) or not _texto_ok(completada.get("texto")):
        errores.append(f"{donde}: finales.completada necesita titulo y texto")
    derrotas = finales.get("derrota")
    if not isinstance(derrotas, list) or not derrotas:
        errores.append(f"{donde}: finales.derrota debe ser una lista con al menos un final")
        return
    anterior = 0
    for final in derrotas:
        tope = final.get("hasta_evento")
        if not isinstance(tope, int) or tope <= anterior:
            errores.append(f"{donde}: 'hasta_evento' de finales.derrota debe ir en orden")
        else:
            anterior = tope
        if not _texto_ok(final.get("titulo")) or not _texto_ok(final.get("texto")):
            errores.append(f"{donde}: cada final de derrota necesita titulo y texto")


def _validar_opcion(opcion, tipo, atributos, donde, errores):
    campos = ["texto", "retroalimentacion"]
    campos += ["desenlace"] if tipo == NORMAL else ["desenlace_exito", "desenlace_fallo"]
    for campo in ["id", *campos]:
        if not _texto_ok(opcion.get(campo)):
            errores.append(f"{donde}: la opcion necesita '{campo}'")
    if tipo == NORMAL:
        if not isinstance(opcion.get("correcta"), bool):
            errores.append(f"{donde}: la opcion '{opcion.get('id')}' necesita correcta: true/false")
        return
    if opcion.get("atributo") not in atributos:
        errores.append(
            f"{donde}: la opcion '{opcion.get('id')}' usa el atributo "
            f"'{opcion.get('atributo')}', que no existe en config_juego.json"
        )
    base = opcion.get("probabilidad_base")
    if not isinstance(base, int) or isinstance(base, bool) or not 0 <= base <= 100:
        errores.append(f"{donde}: probabilidad_base de '{opcion.get('id')}' debe ser 0 a 100")


def _validar_evento(evento, tipo, subtemas, atributos, ids_vistos, nombre_archivo, errores):
    eid = evento.get("id", "(sin id)")
    donde = f"{nombre_archivo} > {eid}"
    if not _texto_ok(evento.get("id")):
        errores.append(f"{nombre_archivo}: hay un evento sin 'id'")
    elif eid in ids_vistos:
        errores.append(f"{donde}: id de evento repetido")
    ids_vistos.add(eid)
    if evento.get("subtema") not in subtemas:
        errores.append(f"{donde}: el subtema '{evento.get('subtema')}' no esta en 'subtemas'")
    for campo in ("titulo", "contexto"):
        if not _texto_ok(evento.get(campo)):
            errores.append(f"{donde}: falta '{campo}'")
    opciones = evento.get("opciones", [])
    if not MIN_OPCIONES <= len(opciones) <= MAX_OPCIONES:
        errores.append(f"{donde}: debe tener entre {MIN_OPCIONES} y {MAX_OPCIONES} opciones")
    if len({o.get("id") for o in opciones}) != len(opciones):
        errores.append(f"{donde}: los ids de las opciones se repiten")
    for opcion in opciones:
        _validar_opcion(opcion, tipo, atributos, donde, errores)
    if tipo == NORMAL and sum(1 for o in opciones if o.get("correcta") is True) != 1:
        errores.append(f"{donde}: un evento normal necesita exactamente una opcion correcta")


def _validar_tema(nombre_archivo, datos, atributos, ids_vistos, errores):
    for clave in ("tema", "subtemas", *CLAVES_EVENTOS.values()):
        if clave not in datos:
            errores.append(f"{nombre_archivo}: falta la clave '{clave}'")
            return
    tema = datos["tema"]
    if not _texto_ok(tema.get("id")) or not _texto_ok(tema.get("nombre")):
        errores.append(f"{nombre_archivo}: 'tema' necesita id y nombre")
    subtemas = {s.get("id") for s in datos["subtemas"]}
    cubiertos = {NORMAL: set(), PROBABILIDAD: set()}
    for tipo, clave in CLAVES_EVENTOS.items():
        for evento in datos[clave]:
            _validar_evento(evento, tipo, subtemas, atributos, ids_vistos, nombre_archivo, errores)
            cubiertos[tipo].add(evento.get("subtema"))
    for subtema in sorted(s for s in subtemas if s):
        for tipo in (NORMAL, PROBABILIDAD):
            if subtema not in cubiertos[tipo]:
                errores.append(f"{nombre_archivo}: el subtema '{subtema}' no tiene evento '{tipo}'")


def _construir():
    errores = []
    config = _leer(CONFIG_PATH, errores)
    if config is not None:
        _validar_config(config, errores)
    atributos = {a.get("id") for a in (config or {}).get("atributos", [])}

    temas, eventos, ids_vistos = {}, {}, set()
    for ruta in sorted(ESCENARIOS_DIR.glob("*.json")):
        datos = _leer(ruta, errores)
        if datos is None:
            continue
        antes = len(errores)
        _validar_tema(ruta.name, datos, atributos, ids_vistos, errores)
        if len(errores) > antes:
            continue
        tema = datos["tema"]
        nombres = {s["id"]: s["nombre"] for s in datos["subtemas"]}
        temas[tema["id"]] = {
            "id": tema["id"],
            "nombre": tema["nombre"],
            "descripcion": tema.get("descripcion", ""),
            "subtemas": datos["subtemas"],
        }
        for tipo, clave in CLAVES_EVENTOS.items():
            for evento in datos[clave]:
                eventos[evento["id"]] = {
                    **evento,
                    "tipo": tipo,
                    "tema_id": tema["id"],
                    "tema_nombre": tema["nombre"],
                    "subtema_nombre": nombres[evento["subtema"]],
                }
    if not temas and not errores:
        errores.append("No hay archivos de escenarios en app/data/escenarios/")
    return config, {"temas": temas, "eventos": eventos}, errores


def validar():
    """Devuelve la lista de errores de los archivos (vacia si todo esta bien)."""
    return _construir()[2]


def cargar():
    """Devuelve (config, catalogo). Relee los JSON si cambiaron. Lanza CatalogoError."""
    firma = _firma()
    if _cache["firma"] != firma:
        _cache["firma"] = firma
        _cache["resultado"] = _construir()
    config, catalogo, errores = _cache["resultado"]
    if errores:
        raise CatalogoError(errores)
    return config, catalogo
