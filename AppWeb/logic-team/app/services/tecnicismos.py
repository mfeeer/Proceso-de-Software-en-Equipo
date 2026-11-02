"""Tecnicismos: catalogo, validacion y registro por jugador.

Cambios del CU01 que pide el SRS para el CU05 (RF-39 a RF-41):
  RF-39  el libro resalta con otro color los tecnicismos del evento (js/tecnicismos.js)
  RF-40  al presionar un tecnicismo se muestra su explicacion (js/tecnicismos.js)
  RF-41  el tecnicismo se registra la primera vez que aparece en un evento; el registro es
         acumulativo, se conserva entre partidas y no se duplica (CU05-RN02, registrar())

El catalogo vive en app/data/tecnicismos.json (RNF-MAN-07) y cada evento de los escenarios
declara en "tecnicismos" los que aparecen en su texto. escenarios.cargar() lee y valida este
archivo junto con los escenarios, asi que un error aqui se reporta igual que uno de escenarios
(y lo detecta el comando validar_escenarios).

Jugador: el registro y el historial son por usuario (SDS 1.3.5). Si nadie ha iniciado sesion,
se guardan con la clave de la sesion del navegador, para que el modo funcione en la demo.
"""

import re
from dataclasses import dataclass

from django.db import IntegrityError, transaction

CLAVES_REGLAS = (
    "minimo_tecnicismos",
    "preguntas_por_cuestionario",
    "opciones_por_pregunta",
    "dias_validez_cuestionario",
)
CAMPOS_OBLIGATORIOS = ("id", "nombre", "subtema", "descripcion", "palabra_clave")


# ---------------------------------------------------------------- jugador
@dataclass(frozen=True)
class Jugador:
    """Dueño del registro de tecnicismos y del historial del cuestionario."""

    usuario: object = None  # instancia de User o None
    sesion: str = ""

    @property
    def clave(self):
        return f"u:{self.usuario.pk}" if self.usuario is not None else f"s:{self.sesion}"

    def filtro(self):
        if self.usuario is not None:
            return {"usuario": self.usuario}
        return {"usuario__isnull": True, "sesion": self.sesion}

    def campos(self):
        if self.usuario is not None:
            return {"usuario": self.usuario, "sesion": ""}
        return {"usuario": None, "sesion": self.sesion}


def jugador_de(request):
    """Jugador de la peticion: el usuario con sesion iniciada o, si no hay, la sesion."""
    if request.user.is_authenticated:
        return Jugador(usuario=request.user)
    if not request.session.session_key:
        request.session.save()
    return Jugador(sesion=request.session.session_key)


# ---------------------------------------------------------------- texto
def patron(forma):
    """Expresion que encuentra la forma como palabra completa, sin importar mayusculas."""
    return re.compile(r"(?<!\w)" + re.escape(forma) + r"(?!\w)", re.IGNORECASE)


def aparece(tecnicismo, texto):
    return any(patron(forma).search(texto or "") for forma in tecnicismo["formas"])


def texto_visible(evento):
    """Lo que el usuario lee al llegar al evento: la situacion y las opciones."""
    opciones = [o.get("texto", "") for o in evento.get("opciones", [])]
    return " ".join([evento.get("contexto", ""), *opciones])


# ---------------------------------------------------------------- catalogo
def _texto_ok(valor):
    return isinstance(valor, str) and valor.strip() != ""


def _validar_reglas(reglas, donde, errores):
    if not isinstance(reglas, dict):
        errores.append(f"{donde}: falta el bloque 'reglas'")
        return
    for clave in CLAVES_REGLAS:
        valor = reglas.get(clave)
        if not isinstance(valor, int) or isinstance(valor, bool) or valor < 1:
            errores.append(f"{donde}: reglas.{clave} debe ser un entero mayor a 0")
    opciones = reglas.get("opciones_por_pregunta")
    minimo = reglas.get("minimo_tecnicismos")
    if isinstance(opciones, int) and isinstance(minimo, int) and minimo < opciones:
        errores.append(
            f"{donde}: reglas.minimo_tecnicismos no puede ser menor que opciones_por_pregunta"
        )


def _validar_tecnicismo(tec, donde, errores):
    tid = tec.get("id", "(sin id)")
    for campo in CAMPOS_OBLIGATORIOS:
        if not _texto_ok(tec.get(campo)):
            errores.append(f"{donde} > {tid}: falta '{campo}'")
    escenario = tec.get("escenario_aplicacion")
    if escenario is not None and not isinstance(escenario, str):
        errores.append(f"{donde} > {tid}: 'escenario_aplicacion' debe ser texto (o no ponerlo)")
    formas = tec.get("formas")
    if not isinstance(formas, list) or not formas or not all(_texto_ok(f) for f in formas):
        errores.append(f"{donde} > {tid}: 'formas' debe ser una lista de textos no vacia")
    clave = tec.get("palabra_clave")
    if _texto_ok(clave) and _texto_ok(tec.get("descripcion")):
        if not patron(clave).search(tec["descripcion"]):
            errores.append(
                f"{donde} > {tid}: la palabra_clave '{clave}' debe aparecer en la descripcion "
                "como palabra completa (la usa la pregunta tipo C)"
            )


def _repetidos(valores):
    vistos, repetidos = set(), set()
    for valor in valores:
        llave = valor.strip().casefold()
        (repetidos if llave in vistos else vistos).add(llave)
    return repetidos


def leer(datos, donde, errores):
    """Valida el contenido de tecnicismos.json y devuelve (reglas, {id: tecnicismo})."""
    if not isinstance(datos, dict):
        errores.append(f"{donde}: el archivo debe ser un objeto JSON")
        return {}, {}
    _validar_reglas(datos.get("reglas"), donde, errores)
    lista = datos.get("tecnicismos")
    if not isinstance(lista, list) or not lista:
        errores.append(f"{donde}: 'tecnicismos' debe ser una lista no vacia")
        return datos.get("reglas") or {}, {}
    catalogo = {}
    for tec in lista:
        if not isinstance(tec, dict):
            errores.append(f"{donde}: cada tecnicismo debe ser un objeto")
            continue
        _validar_tecnicismo(tec, donde, errores)
        if tec.get("id") in catalogo:
            errores.append(f"{donde} > {tec['id']}: id repetido")
        catalogo[tec.get("id")] = tec
    # Las opciones de una pregunta no pueden repetirse (CU05-RN04)
    for campo in ("nombre", "palabra_clave", "escenario_aplicacion"):
        valores = [t[campo] for t in catalogo.values() if _texto_ok(t.get(campo))]
        for repetido in sorted(_repetidos(valores)):
            errores.append(f"{donde}: el {campo} '{repetido}' se repite en varios tecnicismos")
    return datos.get("reglas") or {}, catalogo


def validar_eventos(eventos, catalogo, donde):
    """Cada evento declara tecnicismos que existen y que se leen en su texto (RF-39)."""
    errores = []
    for evento in eventos:
        ids = evento.get("tecnicismos", [])
        lugar = f"{donde} > {evento.get('id')}"
        if not isinstance(ids, list) or not all(_texto_ok(i) for i in ids):
            errores.append(f"{lugar}: 'tecnicismos' debe ser una lista de ids")
            continue
        if len(set(ids)) != len(ids):
            errores.append(f"{lugar}: hay tecnicismos repetidos")
        visible = texto_visible(evento)
        for tid in ids:
            tec = catalogo.get(tid)
            if tec is None:
                errores.append(f"{lugar}: el tecnicismo '{tid}' no existe en tecnicismos.json")
            elif isinstance(tec.get("formas"), list) and not aparece(tec, visible):
                errores.append(
                    f"{lugar}: el tecnicismo '{tid}' no aparece en el contexto ni en las opciones "
                    f"(formas: {', '.join(tec['formas'])})"
                )
    return errores


def cargar():
    """Devuelve (reglas, catalogo). Lanza escenarios.CatalogoError si hay errores."""
    from . import escenarios

    _, catalogo = escenarios.cargar()
    return catalogo["reglas_cuestionario"], catalogo["tecnicismos"]


def publicos(ids, catalogo):
    """Lo que el navegador necesita para resaltar y explicar (RF-39, RF-40)."""
    return [
        {
            "id": tid,
            "nombre": catalogo[tid]["nombre"],
            "descripcion": catalogo[tid]["descripcion"],
            "formas": catalogo[tid]["formas"],
        }
        for tid in ids
        if tid in catalogo
    ]


# ---------------------------------------------------------------- registro (RF-41, RN02)
def registrados(jugador, catalogo=None):
    """Ids registrados por el jugador que siguen en el catalogo (CU05-RN01)."""
    from app.models import TecnicismoRegistrado

    ids = TecnicismoRegistrado.objects.filter(**jugador.filtro()).values_list(
        "tecnicismo_id", flat=True
    )
    if catalogo is None:
        _, catalogo = cargar()
    return [tid for tid in ids if tid in catalogo]


def registrar(jugador, ids, partida=None):
    """Registra los tecnicismos que el jugador aun no tenia. Devuelve los ids nuevos.

    Acumulativo y sin duplicados: lo garantizan las restricciones unicas del modelo, asi que
    dos pestañas que muestran el mismo evento a la vez no crean registros repetidos.
    """
    from app.models import TecnicismoRegistrado

    ids = list(dict.fromkeys(ids or []))
    if not ids:
        return []
    ya = set(
        TecnicismoRegistrado.objects.filter(**jugador.filtro(), tecnicismo_id__in=ids).values_list(
            "tecnicismo_id", flat=True
        )
    )
    nuevos = []
    for tid in ids:
        if tid in ya:
            continue
        try:
            with transaction.atomic():
                TecnicismoRegistrado.objects.create(
                    **jugador.campos(), tecnicismo_id=tid, partida=partida
                )
            nuevos.append(tid)
        except IntegrityError:
            pass  # otra peticion lo registro al mismo tiempo
    return nuevos


def registrar_del_estado(jugador, estado, partida=None):
    """El CU01 llama esto con el estado del libro: si muestra un evento, registra sus
    tecnicismos y marca en el estado cuales son nuevos para avisar al usuario."""
    if estado.get("fase") != "evento" or not estado.get("tecnicismos"):
        estado["tecnicismos_nuevos"] = []
        return estado
    estado["tecnicismos_nuevos"] = registrar(
        jugador, [t["id"] for t in estado["tecnicismos"]], partida
    )
    return estado
