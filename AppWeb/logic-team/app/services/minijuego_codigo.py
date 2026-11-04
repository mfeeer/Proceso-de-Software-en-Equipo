"""Servicio de codigo del CU-04 Resolver minijuego de codigo (SDS 1.3.4 y 3.3.2).

El minijuego se abre desde el menu de modos (CU-05) y no depende de una partida. Cada nivel es
un programa completo, en Python o en pseudocodigo, con sus lineas revueltas: el jugador las
acomoda en orden y con su sangria hasta que el programa quede como debe ir.

No hay una sola respuesta. Cada linea del nivel declara reglas y vale cualquier acomodo que las
respete, asi cada quien puede programar a su manera (por ejemplo, leer b antes que a):

  sangria     nivel de sangria de la linea (0, 1, 2...)
  padre       la linea que la contiene (if, for, Si, Para, Algoritmo); sin padre va hasta afuera
  sigue_a     la linea cuyo bloque debe terminar justo antes (else, SiNo, FinSi, FinPara...)
  despues_de  lineas que deben aparecer antes, en cualquier lugar del programa

Algunos niveles traen distractores: lineas que no van en el programa.

  iniciar()    -> pasos 1 a 3: abre (o retoma) el IntentoCodigo del jugador para un nivel
  comprobar()  -> pasos 4 a 9: programa vacio (FE3) o incompleto (FE1) no cuentan como fallo;
                  si las reglas no se cumplen es un intento fallido (FE2, RN05) salvo que sea el
                  mismo acomodo que ya fallo (RN02); si se cumplen, califica (RN01, RN03, RN04)
  salir()      -> FA3: el intento queda abandonado, sin XP

El contenido vive en app/data (RNF-MAN-05, RNF-MAN-07): los niveles en niveles_codigo/*.json y
las reglas de estrellas y XP en config_juego.json > minijuego_codigo. Se vuelve a leer solo
cuando cambia.
"""

import hashlib
import json
import random
import re

from django.db import transaction

from app.models import IntentoCodigo

from . import escenarios

NIVELES_DIR = escenarios.DATA_DIR / "niveles_codigo"

LENGUAJES = {"python": "Python", "pseudocodigo": "Pseudocódigo"}
LENGUAJE_INICIAL = "python"
MAX_SANGRIA = 6
MAX_LINEAS = 40  # tope de lo que acepta el servidor, sea cual sea el nivel
MAX_CODIGO = 80  # caracteres por linea
ID_VALIDO = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

_cache = {"firma": None, "resultado": None}


class ReglaCodigo(Exception):
    """El jugador intento algo que las reglas no permiten (la API responde 409)."""


class ProgramaInvalido(Exception):
    """El programa que mando el navegador no tiene la forma esperada (la API responde 400)."""


# ---------------------------------------------------------------- catalogo (contenido en JSON)
def _texto_ok(valor):
    return isinstance(valor, str) and valor.strip() != ""


def _entero(valor, minimo=0, maximo=None):
    if not isinstance(valor, int) or isinstance(valor, bool) or valor < minimo:
        return False
    return maximo is None or valor <= maximo


def _leer(ruta, errores):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errores.append(f"{ruta.name}: JSON invalido (linea {exc.lineno}): {exc.msg}")
    except OSError as exc:
        errores.append(f"{ruta.name}: no se pudo leer ({exc})")
    return None


def _validar_reglas(config, errores):
    donde = f"{escenarios.CONFIG_PATH.name} > minijuego_codigo"
    reglas = config.get("minijuego_codigo")
    if not isinstance(reglas, dict):
        errores.append(f"{escenarios.CONFIG_PATH.name}: falta la clave 'minijuego_codigo'")
        return
    estrellas = reglas.get("estrellas")
    if not isinstance(estrellas, list) or not estrellas:
        errores.append(f"{donde}: 'estrellas' debe ser una lista con al menos una regla")
    else:
        for regla in estrellas:
            if not _entero(regla.get("estrellas"), 1, 5):
                errores.append(f"{donde}: cada regla necesita 'estrellas' de 1 a 5")
            if not _entero(regla.get("porcentaje_xp"), 0, 100):
                errores.append(f"{donde}: 'porcentaje_xp' debe ser de 0 a 100")
            fallos = regla.get("fallos_max")
            if fallos is not None and not _entero(fallos):
                errores.append(f"{donde}: 'fallos_max' debe ser un entero o null")
        if estrellas[-1].get("fallos_max", 0) is not None:
            errores.append(f"{donde}: la ultima regla debe tener fallos_max: null")
    for clave in ("penalizacion_por_fallo", "penalizacion_maxima"):
        if not _entero(reglas.get(clave), 0, 100):
            errores.append(f"{donde}: '{clave}' debe ser de 0 a 100")


def _validar_variante(variante, donde, errores):
    """Lineas, distractores y consola de un programa en un lenguaje."""
    if not isinstance(variante, dict):
        errores.append(f"{donde}: debe ser un objeto con 'lineas'")
        return False
    antes = len(errores)
    lineas = variante.get("lineas")
    distractores = variante.get("distractores", [])
    if not isinstance(lineas, list) or not 2 <= len(lineas) <= MAX_LINEAS:
        errores.append(f"{donde}: 'lineas' debe tener de 2 a {MAX_LINEAS} lineas")
        return False
    if not isinstance(distractores, list):
        errores.append(f"{donde}: 'distractores' debe ser una lista")
        return False
    if len(lineas) + len(distractores) > MAX_LINEAS:
        errores.append(f"{donde}: hay mas de {MAX_LINEAS} lineas contando los distractores")

    ids, codigos = set(), set()
    for linea in [*lineas, *distractores]:
        lid, codigo = linea.get("id"), linea.get("codigo")
        if not _texto_ok(lid) or lid in ids:
            errores.append(f"{donde}: cada linea necesita un 'id' unico")
            continue
        ids.add(lid)
        if not _texto_ok(codigo) or len(codigo) > MAX_CODIGO:
            errores.append(f"{donde} > {lid}: 'codigo' debe tener de 1 a {MAX_CODIGO} caracteres")
        elif codigo.strip() in codigos:
            # Dos lineas iguales serian intercambiables y una contaria como mal puesta
            errores.append(f"{donde} > {lid}: el codigo «{codigo}» se repite")
        else:
            codigos.add(codigo.strip())

    reales = {linea.get("id"): linea for linea in lineas}
    for linea in lineas:
        lid = linea.get("id")
        sangria, padre = linea.get("sangria"), linea.get("padre")
        if not _entero(sangria, 0, MAX_SANGRIA):
            errores.append(f"{donde} > {lid}: 'sangria' debe ser de 0 a {MAX_SANGRIA}")
            continue
        if padre is None and sangria != 0:
            errores.append(f"{donde} > {lid}: con sangria {sangria} necesita un 'padre'")
        elif padre is not None and (
            padre not in reales or reales[padre].get("sangria") != sangria - 1
        ):
            errores.append(
                f"{donde} > {lid}: 'padre' debe ser una linea con un nivel menos de sangria"
            )
        sigue = linea.get("sigue_a")
        if sigue is not None and (sigue not in reales or reales[sigue].get("padre") != padre):
            errores.append(f"{donde} > {lid}: 'sigue_a' debe ser una linea con el mismo padre")
        previas = linea.get("despues_de", [])
        if not isinstance(previas, list) or not all(p in reales and p != lid for p in previas):
            errores.append(f"{donde} > {lid}: 'despues_de' debe listar ids de otras lineas")

    consola = variante.get("consola")
    if (
        not isinstance(consola, list)
        or not consola
        or not all(
            isinstance(c, dict)
            and isinstance(c.get("texto"), str)
            and isinstance(c.get("entrada", ""), str)
            for c in consola
        )
    ):
        errores.append(f"{donde}: 'consola' debe ser una lista de {{texto, entrada}}")
    return len(errores) == antes


def _validar_nivel(datos, nombre, errores):
    """Devuelve los niveles (uno por lenguaje) del programa o [] si tiene errores."""
    donde = f"niveles_codigo/{nombre}"
    antes = len(errores)
    pid = datos.get("id")
    if not _texto_ok(pid) or not ID_VALIDO.match(pid):
        errores.append(f"{donde}: 'id' debe usar minusculas, numeros y guiones")
    for campo in ("titulo", "objetivo"):
        if not _texto_ok(datos.get(campo)):
            errores.append(f"{donde}: falta '{campo}'")
    for clave in ("xp_base", "orden"):
        if not _entero(datos.get(clave, 0), 0):
            errores.append(f"{donde}: '{clave}' debe ser un entero de 0 en adelante")
    variantes = datos.get("lenguajes")
    if not isinstance(variantes, dict) or not variantes:
        errores.append(f"{donde}: 'lenguajes' necesita al menos {' o '.join(LENGUAJES)}")
        return []
    for lenguaje in variantes:
        if lenguaje not in LENGUAJES:
            errores.append(f"{donde}: el lenguaje '{lenguaje}' no existe ({', '.join(LENGUAJES)})")
    if len(errores) != antes:
        return []

    niveles = []
    for lenguaje, variante in variantes.items():
        lugar = f"{donde} > {lenguaje}"
        if not _validar_variante(variante, lugar, errores):
            continue
        nivel_ = {
            "id": f"{pid}-{lenguaje}",
            "programa": pid,
            "lenguaje": lenguaje,
            "orden": datos.get("orden", 0),
            "titulo": datos["titulo"],
            "objetivo": datos["objetivo"],
            "xp_base": datos["xp_base"],
            "lineas": variante["lineas"],
            "distractores": variante.get("distractores", []),
            "consola": variante["consola"],
        }
        # Las lineas, en el orden en que vienen, deben ser una solucion valida
        solucion = [{"id": ln["id"], "sangria": ln["sangria"]} for ln in nivel_["lineas"]]
        revision = revisar_programa(solucion, nivel_)
        if not revision["correcta"]:
            motivo = (
                revision["errores"][0]["mensaje"] if revision["errores"] else revision["mensaje"]
            )
            errores.append(f"{lugar}: las lineas en su orden no cumplen sus reglas ({motivo})")
            continue
        niveles.append(nivel_)
    return niveles


def _archivos():
    return [escenarios.CONFIG_PATH, *sorted(NIVELES_DIR.glob("*.json"))]


def _firma():
    return tuple((str(r), r.stat().st_mtime_ns) for r in _archivos() if r.exists())


def _construir():
    errores = []
    config = _leer(escenarios.CONFIG_PATH, errores) or {}
    _validar_reglas(config, errores)

    niveles, programas = [], set()
    for ruta in sorted(NIVELES_DIR.glob("*.json")):
        datos = _leer(ruta, errores)
        if datos is None:
            continue
        if not isinstance(datos, dict):
            errores.append(f"niveles_codigo/{ruta.name}: el archivo debe ser un objeto JSON")
            continue
        if datos.get("id") in programas:
            errores.append(f"niveles_codigo/{ruta.name}: id de programa repetido")
            continue
        programas.add(datos.get("id"))
        niveles += _validar_nivel(datos, ruta.name, errores)
    if not niveles and not errores:
        errores.append("No hay niveles en app/data/niveles_codigo/")
    orden = list(LENGUAJES)
    niveles.sort(key=lambda n: (orden.index(n["lenguaje"]), n["orden"], n["programa"]))
    catalogo = {
        "reglas": config.get("minijuego_codigo"),
        "programas": len(programas),
        "niveles": {n["id"]: n for n in niveles},
    }
    return catalogo, errores


def validar():
    """Errores de las reglas y de los niveles (vacia si todo esta bien)."""
    return _construir()[1]


def cargar():
    """Devuelve {"reglas", "programas", "niveles"}. Lanza escenarios.CatalogoError."""
    firma = _firma()
    if _cache["firma"] != firma:
        _cache["firma"] = firma
        _cache["resultado"] = _construir()
    catalogo, errores = _cache["resultado"]
    if errores:
        raise escenarios.CatalogoError(errores)
    return catalogo


def nivel(nivel_id):
    """El nivel o None si no existe."""
    return cargar()["niveles"].get(nivel_id)


def niveles_de(lenguaje):
    """Niveles de un lenguaje, en orden."""
    return [n for n in cargar()["niveles"].values() if n["lenguaje"] == lenguaje]


# ---------------------------------------------------------------- programa que manda el navegador
def leer_programa(datos, nivel_):
    """Convierte {"programa": [{"id", "sangria"}, ...]} en lineas limpias (SDS 3.3.2)."""
    lista = datos.get("programa") if isinstance(datos, dict) else None
    if not isinstance(lista, list) or len(lista) > MAX_LINEAS:
        raise ProgramaInvalido("El programa no tiene un formato válido.")
    conocidas = {ln["id"] for ln in [*nivel_["lineas"], *nivel_["distractores"]]}
    programa, vistas = [], set()
    for linea in lista:
        if not isinstance(linea, dict):
            raise ProgramaInvalido("El programa no tiene un formato válido.")
        lid, sangria = linea.get("id"), linea.get("sangria")
        if lid not in conocidas:
            raise ProgramaInvalido("Esa línea no es de este nivel.")
        if lid in vistas:
            raise ProgramaInvalido("Cada línea solo se puede usar una vez.")
        if not _entero(sangria, 0, MAX_SANGRIA):
            raise ProgramaInvalido(f"La sangría debe ser de 0 a {MAX_SANGRIA}.")
        vistas.add(lid)
        programa.append({"id": lid, "sangria": sangria})
    return programa


def huella(programa):
    """Huella del acomodo: si cambia una linea o su sangria, cambia la huella (RN02)."""
    texto = json.dumps(programa, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- revisar el acomodo (FE1-FE3)
def _cita(linea):
    return f"«{linea['codigo'].strip()}»"


def revisar_programa(programa, nivel_):
    """Revisa el acomodo contra las reglas de cada linea, de arriba hacia abajo.

    Devuelve {"completo", "correcta", "errores", "titulo", "mensaje", "faltan"}. Cada error
    trae la linea que se marca en rojo, una nota corta y el mensaje completo; el mensaje
    principal es el del primer error para no abrumar.
    """
    reales = {ln["id"]: ln for ln in nivel_["lineas"]}
    distractores = {d["id"]: d for d in nivel_["distractores"]}
    usadas = {p["id"] for p in programa}
    faltan = sum(1 for lid in reales if lid not in usadas)
    base = {"completo": False, "correcta": False, "errores": [], "faltan": faltan}

    if not programa:  # FE3
        return {
            **base,
            "vacio": True,
            "titulo": "El programa está vacío",
            "mensaje": "Pasa las líneas del banco al programa y acomódalas.",
        }
    if faltan:  # FE1: no se califica hasta que estén todas
        return {
            **base,
            "vacio": False,
            "titulo": "Te faltan líneas",
            "mensaje": f"Todavía quedan {faltan} {'línea' if faltan == 1 else 'líneas'} "
            "del programa en el banco.",
        }

    errores = []

    def error(linea_id, nota, mensaje):
        errores.append({"linea_id": linea_id, "nota": nota, "mensaje": mensaje})

    for p in programa:
        if p["id"] in distractores:
            d = distractores[p["id"]]
            error(
                d["id"],
                "esta línea sobra",
                f"{_cita(d)} no forma parte de la solución: regrésala al banco.",
            )

    # La estructura se revisa sin los distractores para no encadenar errores
    acomodo = [p for p in programa if p["id"] in reales]
    posicion = {p["id"]: i for i, p in enumerate(acomodo)}
    ancestros = []  # por posicion: ids de las lineas que la contienen, segun la sangria
    abiertas = []  # pila de (sangria, id) mientras se recorre
    for i, p in enumerate(acomodo):
        linea, sangria = reales[p["id"]], p["sangria"]
        while abiertas and abiertas[-1][0] >= sangria:
            abiertas.pop()
        ancestros.append({lid for _, lid in abiertas})
        padre = abiertas[-1][1] if abiertas else None
        esperado = linea.get("padre")
        if (abiertas and abiertas[-1][0] != sangria - 1) or (not abiertas and sangria != 0):
            error(linea["id"], "sangría de más", f"{_cita(linea)} tiene sangría de más.")
        elif padre != esperado:
            if esperado is None:
                error(
                    linea["id"],
                    "quítale sangría",
                    f"{_cita(linea)} no va dentro de {_cita(reales[padre])}: quítale sangría.",
                )
            elif padre is None:
                error(
                    linea["id"],
                    "dale sangría",
                    f"{_cita(linea)} debe ir dentro de {_cita(reales[esperado])}: dale sangría.",
                )
            else:
                error(
                    linea["id"],
                    "va dentro de otra línea",
                    f"{_cita(linea)} debe ir dentro de {_cita(reales[esperado])}, "
                    f"no de {_cita(reales[padre])}.",
                )
        abiertas.append((sangria, linea["id"]))

        sigue = linea.get("sigue_a")
        if sigue is not None:
            anterior = acomodo[i - 1]["id"] if i else None
            if anterior is None or (anterior != sigue and sigue not in ancestros[i - 1]):
                error(
                    linea["id"],
                    "va justo después de otro bloque",
                    f"{_cita(linea)} debe ir justo después de lo que está dentro de "
                    f"{_cita(reales[sigue])}.",
                )
        for previa in linea.get("despues_de", []):
            if posicion[previa] > i:
                error(
                    linea["id"],
                    "está demasiado arriba",
                    f"{_cita(linea)} debe ir después de {_cita(reales[previa])}.",
                )
                break

    if errores:
        # El primer error en el orden del programa es el que se explica
        orden = {p["id"]: i for i, p in enumerate(programa)}
        errores.sort(key=lambda e: orden[e["linea_id"]])
        return {
            **base,
            "completo": True,
            "errores": errores,
            "titulo": "El programa todavía no funciona",
            "mensaje": errores[0]["mensaje"],
        }
    return {
        **base,
        "completo": True,
        "correcta": True,
        "titulo": "¡El programa funciona!",
        "mensaje": "Todas las líneas están en su lugar.",
    }


# ---------------------------------------------------------------- calificar (RN01, RN03-RN05)
def penalizacion(fallos, reglas):
    return min(reglas["penalizacion_maxima"], fallos * reglas["penalizacion_por_fallo"])


def calificar(fallos, nivel_, reglas):
    """Estrellas segun los intentos fallidos y XP con penalizacion por fallos."""
    regla = next(
        r for r in reglas["estrellas"] if r["fallos_max"] is None or fallos <= r["fallos_max"]
    )
    castigo = penalizacion(fallos, reglas)
    base = round(nivel_["xp_base"] * regla["porcentaje_xp"] / 100)
    return {
        "estrellas": regla["estrellas"],
        "estrellas_max": max(r["estrellas"] for r in reglas["estrellas"]),
        "lineas": len(nivel_["lineas"]),
        "xp_base": base,
        "porcentaje_xp": regla["porcentaje_xp"],
        "intentos_fallidos": fallos,
        "penalizacion": castigo,
        "xp": round(base * (100 - castigo) / 100),
    }


# ---------------------------------------------------------------- intentos del jugador
def _de_jugador(jugador):
    return IntentoCodigo.objects.filter(**jugador.filtro())


def _mejores(jugador):
    """Mejores estrellas del jugador en cada nivel resuelto."""
    mejores = {}
    for nivel_id, estrellas in (
        _de_jugador(jugador)
        .filter(estado=IntentoCodigo.RESUELTO)
        .values_list("nivel_id", "estrellas")
    ):
        mejores[nivel_id] = max(mejores.get(nivel_id, 0), estrellas or 0)
    return mejores


def lenguaje_para(jugador, pedido=None):
    """El lenguaje que se pidio o, si no, el del ultimo intento del jugador."""
    if pedido in LENGUAJES:
        return pedido
    niveles = cargar()["niveles"]
    for nivel_id in _de_jugador(jugador).values_list("nivel_id", flat=True)[:20]:
        if nivel_id in niveles:
            return niveles[nivel_id]["lenguaje"]
    return LENGUAJE_INICIAL


def nivel_para(jugador, lenguaje=None):
    """Nivel con el que abre el modo: el primero que el jugador no ha resuelto en ese lenguaje."""
    lenguaje = lenguaje_para(jugador, lenguaje)
    niveles = niveles_de(lenguaje) or list(cargar()["niveles"].values())
    resueltos = _mejores(jugador)
    return next((n["id"] for n in niveles if n["id"] not in resueltos), niveles[0]["id"])


def resumen_jugador(jugador):
    """Para la tarjeta del menu de modos: niveles resueltos y mejores estrellas."""
    catalogo = cargar()
    mejores = {k: v for k, v in _mejores(jugador).items() if k in catalogo["niveles"]}
    maximo = max(r["estrellas"] for r in catalogo["reglas"]["estrellas"])
    return {
        "niveles": len(catalogo["niveles"]),
        "resueltos": len(mejores),
        "estrellas": sum(mejores.values()),
        "estrellas_max": maximo * len(catalogo["niveles"]),
    }


@transaction.atomic
def iniciar(jugador, nivel_id, nuevo=False):
    """Pasos 1 a 3: retoma el intento en curso del nivel o abre uno nuevo.

    Recargar la pagina devuelve el mismo intento con su ultimo acomodo comprobado. Si el ultimo
    intento ya se resolvio, se muestra su resultado hasta que el jugador pida jugar otra vez.
    """
    if nivel(nivel_id) is None:
        raise ReglaCodigo("Ese nivel no existe.")
    ultimo = _de_jugador(jugador).filter(nivel_id=nivel_id).first()
    if ultimo is not None and not nuevo and ultimo.estado != IntentoCodigo.ABANDONADO:
        return ultimo
    if ultimo is not None and ultimo.estado == IntentoCodigo.EN_CURSO:
        ultimo.estado = IntentoCodigo.ABANDONADO  # «Jugar otra vez» sin haber terminado
        ultimo.save(update_fields=["estado", "actualizado"])
    return IntentoCodigo.objects.create(nivel_id=nivel_id, **jugador.campos())


def _en_curso(intento):
    if intento.estado == IntentoCodigo.RESUELTO:
        raise ReglaCodigo("Ya resolviste este nivel. Presiona «Jugar otra vez» para repetirlo.")
    if intento.estado != IntentoCodigo.EN_CURSO:
        raise ReglaCodigo("Saliste de este intento. Vuelve a abrir el minijuego desde el menú.")
    catalogo = cargar()
    nivel_ = catalogo["niveles"].get(intento.nivel_id)
    if nivel_ is None:
        raise ReglaCodigo("Este nivel ya no existe.")
    return catalogo, nivel_


def revolver(nivel_, semilla):
    """Lineas y distractores revueltos, siempre igual para el mismo intento.

    Nunca salen en el orden de la solucion.
    """
    banco = [
        {"id": ln["id"], "codigo": ln["codigo"]}
        for ln in [*nivel_["lineas"], *nivel_["distractores"]]
    ]
    solucion = [ln["id"] for ln in nivel_["lineas"]]
    random.Random(semilla).shuffle(banco)
    if [b["id"] for b in banco[: len(solucion)]] == solucion:
        banco.append(banco.pop(0))
    return banco


def estado_publico(intento, jugador):
    """Lo que necesita la mesa de trabajo (minijuego_codigo.html). Sin las reglas del nivel."""
    catalogo = cargar()
    nivel_ = catalogo["niveles"][intento.nivel_id]
    reglas = catalogo["reglas"]
    mejores = _mejores(jugador)
    otros = {
        n["programa"]: n["id"]
        for n in catalogo["niveles"].values()
        if n["lenguaje"] != nivel_["lenguaje"]
    }
    return {
        "intento_id": str(intento.id),
        "estado": intento.estado,
        "nivel": {
            "id": nivel_["id"],
            "titulo": nivel_["titulo"],
            "objetivo": nivel_["objetivo"],
            "lenguaje": nivel_["lenguaje"],
            "lenguaje_nombre": LENGUAJES[nivel_["lenguaje"]],
            "xp_base": nivel_["xp_base"],
            "distractores": len(nivel_["distractores"]),
            "lineas": revolver(nivel_, str(intento.id)),
            "consola": nivel_["consola"],
        },
        # Selector de niveles del mismo lenguaje y el mismo programa en el otro lenguaje
        "niveles": [
            {
                "id": n["id"],
                "numero": i + 1,
                "titulo": n["titulo"],
                "estrellas": mejores.get(n["id"], 0),
            }
            for i, n in enumerate(niveles_de(nivel_["lenguaje"]))
        ],
        "lenguajes": [
            {
                "id": lenguaje,
                "nombre": nombre,
                "nivel_id": nivel_["id"]
                if lenguaje == nivel_["lenguaje"]
                else otros.get(nivel_["programa"]),
            }
            for lenguaje, nombre in LENGUAJES.items()
        ],
        "programa": intento.tablero or [],
        "intentos_fallidos": intento.intentos_fallidos,
        "penalizacion": penalizacion(intento.intentos_fallidos, reglas),
        "penalizacion_por_fallo": reglas["penalizacion_por_fallo"],
        "penalizacion_maxima": reglas["penalizacion_maxima"],
        "resultado": intento.resultado if intento.estado == IntentoCodigo.RESUELTO else None,
    }


def comprobar(intento, datos):
    """Pasos 4 a 9: revisa el acomodo y, si funciona, califica."""
    catalogo, nivel_ = _en_curso(intento)
    reglas = catalogo["reglas"]
    programa = leer_programa(datos, nivel_)
    revision = revisar_programa(programa, nivel_)
    calificacion = None
    repetido = False
    if revision["completo"]:
        marca = huella(programa)
        repetido = not revision["correcta"] and marca == intento.huella
        intento.tablero = programa
        intento.huella = marca
        intento.bloques_usados = len(programa)
        if revision["correcta"]:
            calificacion = calificar(intento.intentos_fallidos, nivel_, reglas)
            intento.estado = IntentoCodigo.RESUELTO
            intento.estrellas = calificacion["estrellas"]
            intento.xp_obtenida = calificacion["xp"]
            intento.resultado = calificacion
        elif not repetido:  # FE2, RN05; el mismo acomodo no se cobra dos veces (RN02)
            intento.intentos_fallidos += 1
        intento.save()
    return {
        **revision,
        "repetido": repetido,
        "resultado": calificacion,
        "consola": nivel_["consola"] if calificacion else None,
        "intentos_fallidos": intento.intentos_fallidos,
        "penalizacion": penalizacion(intento.intentos_fallidos, reglas),
    }


def salir(intento):
    """FA3: se pierde la solucion y no se gana XP. Un intento ya resuelto no cambia."""
    if intento.estado == IntentoCodigo.EN_CURSO:
        intento.estado = IntentoCodigo.ABANDONADO
        intento.save(update_fields=["estado", "actualizado"])
    return intento
