"""Servicio del CU-06 Conseguir vidas: las reglas del minijuego, sin nada de HTTP.

Diseño: SDS (WP.12) secciones 1.3.6 y 3.3.1, y Figura 9 (diagrama de secuencia).

Con 1 o 2 vidas el usuario abre el minijuego, responde una ronda de afirmaciones de verdadero o
falso y, si acierta el minimo (CU06-RN01), gana 1 vida sin pasar del maximo. Mientras le falten
vidas, cada cinco eventos completados el libro le sugiere el minijuego (FA1).

Todo el estado vive en Partida.vidas_extra (JSON):
    eventos      eventos completados con vidas faltantes desde la ultima sugerencia (FA1)
    sugerir      True cuando el conteo llega a eventos_para_sugerencia
    rondas       rondas iniciadas en la partida
    recuperadas  vidas recuperadas en la partida (cuentan como dano para "Sin rasgunos")
    vistas       ids de las afirmaciones que ya salieron en la partida (no se repiten)
    ronda        la ronda en juego o None: {preguntas, respuestas, resultados, aciertos, ultima,
                 terminada, exito, vidas_ganadas}. Una ronda terminada se queda hasta salir()
                 para que el resultado se pueda volver a mostrar si se recarga la pagina.

Las afirmaciones viven en app/data/preguntas_vidas.json y las reglas en
config_juego.json > conseguir_vidas. El servidor evalua cada respuesta: la pregunta en juego
nunca incluye su respuesta; la respuesta correcta y la explicacion solo llegan en "ultima".
"""

import random

from app.models import Partida

from . import escenarios

PREGUNTAS_PATH = escenarios.DATA_DIR / "preguntas_vidas.json"
CLAVES_REGLAS = (
    "preguntas_por_ronda",
    "aciertos_minimos",
    "vidas_por_ronda",
    "eventos_para_sugerencia",
)
EXTRA_INICIAL = {
    "eventos": 0,
    "sugerir": False,
    "rondas": 0,
    "recuperadas": 0,
    "vistas": [],
    "ronda": None,
}

_cache = {"firma": None, "resultado": None}


def _regla(mensaje):
    """Error de reglas del juego: la API lo responde con 409 (ver views_partida._accion)."""
    from .motor_partida import ReglaError  # aqui para evitar el import circular

    return ReglaError(mensaje)


# ---------------------------------------------------------------- reglas y banco de preguntas
def reglas(config):
    return config["conseguir_vidas"]


def _validar_reglas(config, errores):
    donde = f"{escenarios.CONFIG_PATH.name} > conseguir_vidas"
    datos = config.get("conseguir_vidas")
    if not isinstance(datos, dict):
        errores.append(f"{escenarios.CONFIG_PATH.name}: falta la clave 'conseguir_vidas'")
        return
    for clave in CLAVES_REGLAS:
        valor = datos.get(clave)
        if not isinstance(valor, int) or isinstance(valor, bool) or valor < 1:
            errores.append(f"{donde}: '{clave}' debe ser un entero mayor a 0")
    minimo, total = datos.get("aciertos_minimos"), datos.get("preguntas_por_ronda")
    if isinstance(minimo, int) and isinstance(total, int) and minimo > total:
        errores.append(f"{donde}: 'aciertos_minimos' no puede ser mayor que la ronda")


def _validar_pregunta(pregunta, subtemas, ids_vistos, errores):
    donde = PREGUNTAS_PATH.name
    pid = pregunta.get("id")
    if not escenarios._texto_ok(pid):
        errores.append(f"{donde}: hay una afirmacion sin 'id'")
        return False
    if pid in ids_vistos:
        errores.append(f"{donde} > {pid}: id repetido")
    ids_vistos.add(pid)
    antes = len(errores)
    if pregunta.get("subtema") not in subtemas:
        errores.append(f"{donde} > {pid}: el subtema '{pregunta.get('subtema')}' no existe")
    for campo in ("afirmacion", "explicacion"):
        if not escenarios._texto_ok(pregunta.get(campo)):
            errores.append(f"{donde} > {pid}: falta '{campo}'")
    if not isinstance(pregunta.get("respuesta"), bool):
        errores.append(f"{donde} > {pid}: 'respuesta' debe ser true o false")
    return len(errores) == antes


def _construir():
    try:
        config, catalogo = escenarios.cargar()
    except escenarios.CatalogoError as exc:
        return None, exc.errores
    errores = []
    _validar_reglas(config, errores)
    datos = escenarios._leer(PREGUNTAS_PATH, errores)
    if datos is None:
        return None, errores
    subtemas = {
        s["id"]: f"{tema['nombre']} · {s['nombre']}"
        for tema in catalogo["temas"].values()
        for s in tema["subtemas"]
    }
    lista = datos.get("preguntas") if isinstance(datos, dict) else None
    if not isinstance(lista, list):
        errores.append(f"{PREGUNTAS_PATH.name}: falta la lista 'preguntas'")
        lista = []
    preguntas, ids_vistos = {}, set()
    for pregunta in lista:
        if _validar_pregunta(pregunta, subtemas, ids_vistos, errores):
            preguntas[pregunta["id"]] = {**pregunta, "tema": subtemas[pregunta["subtema"]]}
    if not errores and len(preguntas) < config["conseguir_vidas"]["preguntas_por_ronda"]:
        errores.append(f"{PREGUNTAS_PATH.name}: no alcanzan las afirmaciones para una ronda")
    return preguntas, errores


def validar():
    """Errores de preguntas_vidas.json y de config_juego.json > conseguir_vidas."""
    return _construir()[1]


def cargar_preguntas():
    """Afirmaciones por id (con su 'tema' legible). Relee el JSON si cambio. CatalogoError."""
    mtime = PREGUNTAS_PATH.stat().st_mtime_ns if PREGUNTAS_PATH.exists() else None
    firma = (mtime, escenarios._firma())
    if _cache["firma"] != firma:
        _cache["firma"] = firma
        _cache["resultado"] = _construir()
    preguntas, errores = _cache["resultado"]
    if errores:
        raise escenarios.CatalogoError(errores)
    return preguntas


def _elegir_preguntas(partida, preguntas, vistas, cantidad, rng):
    """Primero las de los subtemas de la partida, luego las de sus materias y al final las de
    cualquier materia; en cada grupo, primero las que aun no se han visto en esta partida."""
    subtemas = set(partida.temas)
    materias = {s.split(":")[0] for s in partida.temas}
    vistas = set(vistas)
    grupos = [[] for _ in range(6)]
    for pid, pregunta in sorted(preguntas.items()):
        if pregunta["subtema"] in subtemas:
            cercania = 0
        elif pregunta["subtema"].split(":")[0] in materias:
            cercania = 1
        else:
            cercania = 2
        grupos[cercania + (3 if pid in vistas else 0)].append(pid)
    elegidas = []
    for grupo in grupos:
        rng.shuffle(grupo)
        elegidas.extend(grupo[: cantidad - len(elegidas)])
    rng.shuffle(elegidas)
    return elegidas


# ---------------------------------------------------------------- estado en la partida
def _extra(partida):
    """vidas_extra con todas sus claves (las partidas viejas lo tienen vacio)."""
    extra = {**EXTRA_INICIAL, **(partida.vidas_extra or {})}
    extra["vistas"] = list(extra["vistas"])
    partida.vidas_extra = extra
    return extra


def puede_conseguir(partida):
    """CU06-RN02: partida en curso y 1 o 2 vidas (al menos 1 y menos del maximo)."""
    return partida.estado == Partida.EN_CURSO and 1 <= partida.hp < partida.hp_max


def ronda_en_juego(partida):
    """Hay una ronda sin terminar: el motor de CU-01 no deja tomar decisiones."""
    ronda = (partida.vidas_extra or {}).get("ronda")
    return bool(ronda) and not ronda.get("terminada")


def recuperadas(partida):
    return (partida.vidas_extra or {}).get("recuperadas", 0)


def registrar_evento(partida, hp_antes, config):
    """FA1: lo llama el motor al resolver cada decision (no guarda; guarda el motor).

    Cuenta los eventos completados mientras faltan vidas; el evento en el que se pierde la vida
    no cuenta. Al llegar a eventos_para_sugerencia marca la sugerencia. Sin vidas (FE4) o con
    las vidas completas (FA3) el conteo se detiene y no hay sugerencia.
    """
    extra = _extra(partida)
    if puede_conseguir(partida) and hp_antes < partida.hp_max:
        extra["eventos"] += 1
        if extra["eventos"] >= reglas(config)["eventos_para_sugerencia"]:
            extra["sugerir"] = True
    elif not puede_conseguir(partida):
        extra["eventos"], extra["sugerir"] = 0, False


def _ronda_publica(ronda, preguntas):
    if ronda is None:
        return None
    respondidas = len(ronda["respuestas"])
    total = len(ronda["preguntas"])
    pregunta = None
    if not ronda["terminada"]:
        actual = preguntas.get(ronda["preguntas"][respondidas])
        if actual:
            pregunta = {
                "id": actual["id"],
                "afirmacion": actual["afirmacion"],
                "tema": actual["tema"],
            }
    return {
        "numero": min(respondidas + 1, total),
        "total": total,
        "respondidas": respondidas,
        "aciertos": ronda["aciertos"],
        "resultados": list(ronda["resultados"]),
        "pregunta": pregunta,
        "ultima": ronda["ultima"],
        "terminada": ronda["terminada"],
        "exito": ronda["exito"],
        "vidas_ganadas": ronda["vidas_ganadas"],
    }


def estado_publico(partida, config):
    """Bloque "vidas" del estado de la partida (SDS 3.3.1)."""
    extra = _extra(partida)
    r = reglas(config)
    return {
        "disponible": puede_conseguir(partida),
        "sugerir": extra["sugerir"],
        "eventos": extra["eventos"],
        "eventos_para_sugerencia": r["eventos_para_sugerencia"],
        "preguntas_por_ronda": r["preguntas_por_ronda"],
        "aciertos_minimos": r["aciertos_minimos"],
        "recuperadas": extra["recuperadas"],
        "ronda": _ronda_publica(extra["ronda"], cargar_preguntas()),
    }


# ---------------------------------------------------------------- acciones (API)
def iniciar_ronda(partida, rng=None):
    """Pasos 4-6: crea la ronda o retoma la que esta en juego (recargar no vuelve a sortear)."""
    if not puede_conseguir(partida):
        if partida.estado != Partida.EN_CURSO or partida.hp < 1:
            raise _regla("La partida terminó: ya no puedes recuperar vidas.")  # FE4
        raise _regla("Ya tienes todas tus vidas.")  # FA3
    extra = _extra(partida)
    if ronda_en_juego(partida):
        return partida
    config, _ = escenarios.cargar()
    preguntas = cargar_preguntas()
    elegidas = _elegir_preguntas(
        partida,
        preguntas,
        extra["vistas"],
        reglas(config)["preguntas_por_ronda"],
        rng or random.SystemRandom(),
    )
    extra["vistas"] += [p for p in elegidas if p not in extra["vistas"]]
    extra["ronda"] = {
        "preguntas": elegidas,
        "respuestas": [],
        "resultados": [],
        "aciertos": 0,
        "ultima": None,
        "terminada": False,
        "exito": None,
        "vidas_ganadas": 0,
    }
    extra["rondas"] += 1
    extra["eventos"], extra["sugerir"] = 0, False
    partida.save(update_fields=["vidas_extra", "actualizada"])
    return partida


def responder(partida, respuesta):
    """Pasos 7-10: evalua la afirmacion actual (True = Verdadero, False = Falso).

    En la ultima afirmacion aplica CU06-RN01 (exito), FA3 (vidas completas) y FE1 (sin cambios).
    """
    if not ronda_en_juego(partida):
        raise _regla("No hay ninguna ronda en juego.")
    if not isinstance(respuesta, bool):
        raise _regla("Responde verdadero o falso.")
    config, _ = escenarios.cargar()
    preguntas = cargar_preguntas()
    extra = _extra(partida)
    ronda = extra["ronda"]
    numero = len(ronda["respuestas"]) + 1
    pregunta = preguntas.get(ronda["preguntas"][numero - 1])
    if pregunta is None:  # la afirmacion se borro del JSON a media ronda
        extra["ronda"] = None
        partida.save(update_fields=["vidas_extra", "actualizada"])
        raise _regla("El banco de preguntas cambió. Vuelve a empezar la ronda.")

    acierto = respuesta == pregunta["respuesta"]
    ronda["respuestas"].append(respuesta)
    ronda["resultados"].append(acierto)
    ronda["aciertos"] += int(acierto)
    ronda["ultima"] = {
        "numero": numero,
        "afirmacion": pregunta["afirmacion"],
        "respuesta_usuario": respuesta,
        "respuesta": pregunta["respuesta"],
        "correcta": acierto,
        "explicacion": pregunta["explicacion"],
    }
    campos = ["vidas_extra", "actualizada"]
    if numero >= len(ronda["preguntas"]):
        r = reglas(config)
        ronda["terminada"] = True
        ronda["exito"] = ronda["aciertos"] >= r["aciertos_minimos"]  # CU06-RN01
        if ronda["exito"]:
            ganadas = max(0, min(r["vidas_por_ronda"], partida.hp_max - partida.hp))
            partida.hp += ganadas
            ronda["vidas_ganadas"] = ganadas
            extra["recuperadas"] += ganadas
            campos.append("hp")
            if partida.hp >= partida.hp_max:  # FA3: se detiene el conteo
                extra["eventos"], extra["sugerir"] = 0, False
    partida.save(update_fields=campos)
    return partida


def salir(partida):
    """FE2 (abandonar sin ganar la vida) o paso 11 (cerrar el resultado): la ronda se borra."""
    extra = _extra(partida)
    if extra["ronda"] is not None:
        extra["ronda"] = None
        partida.save(update_fields=["vidas_extra", "actualizada"])
    return partida


def descartar_sugerencia(partida):
    """FA1: el usuario cerro el recuadro ("Ahora no" o "Conseguir vida"); el conteo reinicia."""
    extra = _extra(partida)
    extra["eventos"], extra["sugerir"] = 0, False
    partida.save(update_fields=["vidas_extra", "actualizada"])
    return partida


def leer_respuesta(cuerpo):
    """{"respuesta": true | false}; tambien acepta "verdadero" / "falso"."""
    valor = cuerpo.get("respuesta")
    if isinstance(valor, str):
        valor = {"verdadero": True, "falso": False}.get(valor.strip().lower(), valor)
    return valor
