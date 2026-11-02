"""Servicio del CU05 Completar cuestionario de tecnicismos: reglas del modo, sin nada de HTTP.

Diseño: SDS (WP.12) secciones 1.3.5 y 3.3.3.

  RN01  solo se preguntan tecnicismos que el jugador ya registro
  RN03  se necesitan al menos 4 registrados para desbloquear el modo (FA1)
  RN04  4 opciones con una sola correcta; los distractores salen de otros registrados
  RN05  10 preguntas, o tantas como registrados si son menos; ningun tecnicismo se repite
  RN06  puntaje = aciertos / total de preguntas x 100 (lo recalcula el servidor al guardar)
  RN07  sin retroalimentacion durante el cuestionario (lo cumple js/cuestionario.js)
  FA5   si el tecnicismo no tiene datos para el tipo asignado, se usa otro tipo disponible

Para poder terminar sin conexion (FE1) el cuestionario completo viaja al navegador, con la
respuesta correcta y la explicacion de cada pregunta. Se acepta porque es una practica y no una
evaluacion formal (SDS 1.4). Para que el historial no dependa del navegador, el servidor firma
el cuestionario (django.core.signing): al guardar verifica la firma, que el cuestionario sea del
mismo jugador y recalcula el puntaje.
"""

import random
import uuid
from datetime import timedelta

from django.core import signing
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from . import tecnicismos

SAL_FIRMA = "logicteam.cu05.cuestionario"
TIPOS = ("A", "B", "C")
NOMBRES_TIPO = {"A": "Definición", "B": "Aplicación", "C": "Completar"}
PIDE = {
    "A": "¿Qué tecnicismo es?",
    "B": "¿En qué situación se aplica?",
    "C": "¿Qué palabra falta?",
}
# Dato que se pregunta en cada tipo; los distractores salen del mismo dato de otros tecnicismos
DATO_DEL_TIPO = {"A": "nombre", "B": "escenario_aplicacion", "C": "palabra_clave"}
HUECO = "_____"


class Insuficientes(Exception):
    """FA1: el jugador no tiene el minimo de tecnicismos registrados (RN03)."""

    def __init__(self, registrados, necesarios):
        self.registrados = registrados
        self.necesarios = necesarios
        super().__init__(mensaje_insuficientes(registrados, necesarios))


class ResultadoInvalido(Exception):
    """El resultado enviado no corresponde a un cuestionario valido."""


class CuestionarioAjeno(ResultadoInvalido):
    """El cuestionario lo genero otro jugador."""


def mensaje_insuficientes(registrados, necesarios):
    return (
        f"Has descubierto {registrados} de {necesarios} tecnicismos necesarios. "
        "¡Juega más partidas para desbloquear el cuestionario!"
    )


def puntaje(aciertos, total):
    """RN06: aciertos / total x 100, redondeado al entero mas cercano (,5 hacia arriba)."""
    if total <= 0:
        return 0
    return (aciertos * 200 + total) // (2 * total)


# ---------------------------------------------------------------- generacion (pasos 4 a 6)
def _valor(tec, tipo):
    valor = tec.get(DATO_DEL_TIPO[tipo])
    return valor.strip() if isinstance(valor, str) else ""


def _distractores(tec, tipo, otros):
    """Valores del mismo dato en otros tecnicismos registrados, sin repetir la respuesta."""
    correcta = _valor(tec, tipo).casefold()
    vistos, valores = {correcta}, []
    for otro in otros:
        valor = _valor(otro, tipo)
        if valor and valor.casefold() not in vistos:
            vistos.add(valor.casefold())
            valores.append(valor)
    return valores


def disponible(tec, tipo, otros, opciones):
    """FA5: el tipo sirve si el tecnicismo tiene el dato y hay suficientes distractores."""
    if not _valor(tec, tipo):
        return False
    if tipo == "C" and not tecnicismos.patron(_valor(tec, "C")).search(tec["descripcion"]):
        return False
    return len(_distractores(tec, tipo, otros)) >= opciones - 1


def _enunciado(tec, tipo):
    if tipo == "A":
        return {"nombre": "", "texto": tec["descripcion"]}
    if tipo == "B":
        return {"nombre": tec["nombre"], "texto": tec["descripcion"]}
    texto = tecnicismos.patron(_valor(tec, "C")).sub(HUECO, tec["descripcion"], count=1)
    return {"nombre": tec["nombre"], "texto": texto}


def _explicacion(tec, tipo):
    if tipo == "A":
        return f"{tec['nombre']}: {tec['descripcion']}"
    if tipo == "B":
        escenario = _valor(tec, "B")
        return f"{tec['nombre']} se aplica, por ejemplo, para: {escenario}. {tec['descripcion']}"
    return f"La palabra que falta es «{_valor(tec, 'C')}». {tec['descripcion']}"


def armar_pregunta(numero, tec, otros, rng, opciones=4):
    """Una pregunta del tecnicismo `tec`; `otros` son los demas tecnicismos registrados."""
    asignado = rng.choice(TIPOS)
    resto = [t for t in TIPOS if t != asignado]
    rng.shuffle(resto)
    tipo = next((t for t in [asignado, *resto] if disponible(tec, t, otros, opciones)), None)
    if tipo is None:
        raise ValueError(f"No hay datos suficientes para preguntar '{tec['id']}'")
    correcta = _valor(tec, tipo)
    lista = [correcta, *rng.sample(_distractores(tec, tipo, otros), opciones - 1)]
    rng.shuffle(lista)
    return {
        "numero": numero,
        "tecnicismo_id": tec["id"],
        "tecnicismo": tec["nombre"],
        "tipo": tipo,
        "tipo_nombre": NOMBRES_TIPO[tipo],
        "tipo_asignado": asignado,
        **_enunciado(tec, tipo),
        "pide": PIDE[tipo],
        "opciones": lista,
        "correcta": lista.index(correcta),
        "explicacion": _explicacion(tec, tipo),
    }


def generar_preguntas(ids_registrados, catalogo, reglas, rng):
    """Pasos 4 a 6. Lanza Insuficientes si no se cumple RN03 (FA1)."""
    ids = [tid for tid in dict.fromkeys(ids_registrados) if tid in catalogo]  # RN01
    minimo = reglas["minimo_tecnicismos"]
    if len(ids) < minimo:
        raise Insuficientes(len(ids), minimo)
    cantidad = min(reglas["preguntas_por_cuestionario"], len(ids))  # RN05
    elegidos = rng.sample(ids, cantidad)  # al azar y sin repetir (RN05)
    registrados = [catalogo[tid] for tid in ids]
    preguntas = []
    for numero, tid in enumerate(elegidos, start=1):
        otros = [t for t in registrados if t["id"] != tid]
        rng.shuffle(otros)
        preguntas.append(
            armar_pregunta(numero, catalogo[tid], otros, rng, reglas["opciones_por_pregunta"])
        )
    return preguntas


def crear(jugador, rng=None):
    """Genera un cuestionario nuevo para el jugador, listo para enviarse al navegador."""
    reglas, catalogo = tecnicismos.cargar()
    rng = rng or random.SystemRandom()
    preguntas = generar_preguntas(tecnicismos.registrados(jugador, catalogo), catalogo, reglas, rng)
    cuestionario_id = str(uuid.uuid4())
    generado = timezone.now()
    firmado = {
        "id": cuestionario_id,
        "j": jugador.clave,
        "g": generado.isoformat(),
        "p": [[p["tecnicismo_id"], p["tipo"], p["opciones"], p["correcta"]] for p in preguntas],
    }
    return {
        "cuestionario_id": cuestionario_id,
        "token": signing.dumps(firmado, salt=SAL_FIRMA, compress=True),
        "generado": generado.isoformat(),
        "total": len(preguntas),
        "preguntas": preguntas,
    }


# ---------------------------------------------------------------- resultado (pasos 10 y 11)
def _leer_token(token, jugador, reglas):
    if not isinstance(token, str) or not token:
        raise ResultadoInvalido("Falta el cuestionario.")
    dias = reglas["dias_validez_cuestionario"]
    try:
        firmado = signing.loads(token, salt=SAL_FIRMA, max_age=timedelta(days=dias))
    except signing.SignatureExpired as exc:
        raise ResultadoInvalido(f"El cuestionario venció (más de {dias} días).") from exc
    except signing.BadSignature as exc:
        raise ResultadoInvalido("El cuestionario no es válido.") from exc
    if firmado.get("j") != jugador.clave:
        raise CuestionarioAjeno("Este cuestionario pertenece a otro jugador.")
    return firmado


def _leer_respuestas(respuestas, preguntas):
    if not isinstance(respuestas, list) or len(respuestas) != len(preguntas):
        raise ResultadoInvalido("Hay que responder todas las preguntas.")
    leidas = []
    for respuesta, (_, _, opciones, _) in zip(respuestas, preguntas, strict=True):
        if isinstance(respuesta, bool) or not isinstance(respuesta, int):
            raise ResultadoInvalido("Cada respuesta debe ser el número de una opción.")
        if not 0 <= respuesta < len(opciones):
            raise ResultadoInvalido("Una respuesta no corresponde a ninguna opción.")
        leidas.append(respuesta)
    return leidas


def _leer_fecha(texto, generado):
    """Fecha en que se termino (la manda el navegador; sin conexion puede ser anterior)."""
    ahora = timezone.now()
    fecha = parse_datetime(texto) if isinstance(texto, str) else None
    if fecha is not None and timezone.is_naive(fecha):
        fecha = timezone.make_aware(fecha)
    if fecha is None or fecha > ahora + timedelta(minutes=5):
        return ahora
    return max(fecha, generado)


def calificar(preguntas, respuestas, catalogo):
    """RN06 con las respuestas correctas del token firmado, no con las del navegador."""
    detalle = []
    for (tid, tipo, opciones, correcta), elegida in zip(preguntas, respuestas, strict=True):
        tec = catalogo.get(tid, {})
        detalle.append(
            {
                "tecnicismo_id": tid,
                "tecnicismo": tec.get("nombre", tid),
                "tipo": tipo,
                "elegida": opciones[elegida],
                "correcta": opciones[correcta],
                "acierto": elegida == correcta,
            }
        )
    aciertos = sum(1 for d in detalle if d["acierto"])
    return aciertos, len(detalle), puntaje(aciertos, len(detalle)), detalle


def _datos(resultado, creado):
    return {
        "cuestionario_id": str(resultado.id),
        "puntaje": resultado.puntaje,
        "aciertos": resultado.aciertos,
        "total": resultado.total,
        "fecha": resultado.fecha.isoformat(),
        "origen": resultado.origen,
        "nuevo": creado,
    }


def guardar_resultado(jugador, token, respuestas, fecha=None, pendiente=False):
    """Guarda el resultado en el historial. Devuelve (datos, creado).

    Si el cuestionario ya estaba guardado (reintento al sincronizar, FE1), no lo duplica y
    devuelve el que ya tenia (RNF-CON-03).
    """
    from app.models import ResultadoCuestionario

    reglas, catalogo = tecnicismos.cargar()
    firmado = _leer_token(token, jugador, reglas)
    existente = ResultadoCuestionario.objects.filter(pk=firmado["id"]).first()
    if existente is not None:
        return _datos(existente, False), False
    elegidas = _leer_respuestas(respuestas, firmado["p"])
    aciertos, total, calificacion, detalle = calificar(firmado["p"], elegidas, catalogo)
    generado = parse_datetime(firmado["g"]) or timezone.now()
    origen = ResultadoCuestionario.SINCRONIZADO if pendiente else ResultadoCuestionario.EN_LINEA
    try:
        with transaction.atomic():
            resultado = ResultadoCuestionario.objects.create(
                id=firmado["id"],
                **jugador.campos(),
                fecha=_leer_fecha(fecha, generado),
                puntaje=calificacion,
                aciertos=aciertos,
                total=total,
                respuestas=detalle,
                origen=origen,
            )
    except IntegrityError:  # el mismo resultado llego dos veces al mismo tiempo
        return _datos(ResultadoCuestionario.objects.get(pk=firmado["id"]), False), False
    return _datos(resultado, True), True


# ---------------------------------------------------------------- menu de modos
def resumen_jugador(jugador):
    """Lo que muestra el menu de modos: avance hacia RN03 y el ultimo puntaje."""
    from app.models import ResultadoCuestionario

    reglas, catalogo = tecnicismos.cargar()
    registrados = len(tecnicismos.registrados(jugador, catalogo))
    minimo = reglas["minimo_tecnicismos"]
    ultimo = ResultadoCuestionario.objects.filter(**jugador.filtro()).first()
    return {
        "registrados": registrados,
        "minimo": minimo,
        "total_catalogo": len(catalogo),
        "desbloqueado": registrados >= minimo,
        "preguntas": min(reglas["preguntas_por_cuestionario"], registrados),
        "faltan": max(0, minimo - registrados),
        "mensaje_bloqueado": mensaje_insuficientes(registrados, minimo),
        "medidor": [numero < registrados for numero in range(minimo)],
        "ultimo": ultimo,
    }
