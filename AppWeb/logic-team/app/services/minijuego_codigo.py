"""Servicio de codigo del CU-04 Resolver minijuego de codigo (SDS 1.3.4 y 3.3.2).

El minijuego se abre desde el menu de modos (CU-05) y no depende de una partida. El jugador
arma un algoritmo con bloques: INBOX lee el siguiente dato y lo guarda en una variable con
nombre (A, B), OUTBOX entrega una variable, COPY_TO copia una variable en otra y SI compara dos
variables y sigue una de sus dos ramas.

  iniciar()   -> pasos 1 a 3: abre (o retoma) el IntentoCodigo del jugador para un nivel
  compilar()  -> pasos 4 y 5: tablero vacio (FE3), bloques sueltos o incompletos (FE1, RN02);
                 si compila, guarda el tablero y su huella
  ejecutar()  -> pasos 6 a 9: solo el tablero compilado (RN02); corre todos los casos de prueba
                 con limite de pasos (FE2) y califica: estrellas (RN01, RN03) y XP (RN04, RN05)
  salir()     -> FA3: el intento queda abandonado, sin XP

El contenido vive en app/data (RNF-MAN-05, RNF-MAN-07): los bloques en
instrucciones_codigo.json, los niveles en niveles_codigo/*.json y las reglas de estrellas y XP
en config_juego.json > minijuego_codigo. Se vuelve a leer solo cuando cambia.
"""

import hashlib
import json
import operator

from django.db import transaction

from app.models import IntentoCodigo

from . import escenarios

INSTRUCCIONES_PATH = escenarios.DATA_DIR / "instrucciones_codigo.json"
NIVELES_DIR = escenarios.DATA_DIR / "niveles_codigo"

TIPOS = {"entrada", "salida", "memoria", "condicion"}
# Parametros que el tablero manda para cada tipo de instruccion
PARAMETROS = {
    "entrada": ("destino",),
    "salida": ("valor",),
    "memoria": ("origen", "destino"),
    "condicion": ("izq", "op", "der"),
}
OPERADORES = {
    ">": (operator.gt, ">"),
    "<": (operator.lt, "<"),
    "==": (operator.eq, "="),
    "!=": (operator.ne, "≠"),
    ">=": (operator.ge, "≥"),
    "<=": (operator.le, "≤"),
}
MAX_PROFUNDIDAD = 4  # un SI dentro de otro, hasta 4 niveles
MAX_BLOQUES_TABLERO = 60  # tope de lo que acepta el servidor, sea cual sea el nivel

_cache = {"firma": None, "resultado": None}


class ReglaCodigo(Exception):
    """El jugador intento algo que las reglas no permiten (la API responde 409)."""


class TableroInvalido(Exception):
    """El tablero que mando el navegador no tiene la forma esperada (la API responde 400)."""


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
            extra = regla.get("bloques_extra_max")
            if extra is not None and not _entero(extra):
                errores.append(f"{donde}: 'bloques_extra_max' debe ser un entero o null")
        if estrellas[-1].get("bloques_extra_max", 0) is not None:
            errores.append(f"{donde}: la ultima regla debe tener bloques_extra_max: null")
    for clave in ("penalizacion_por_fallo", "penalizacion_maxima"):
        if not _entero(reglas.get(clave), 0, 100):
            errores.append(f"{donde}: '{clave}' debe ser de 0 a 100")


def _validar_instrucciones(datos, errores):
    donde = INSTRUCCIONES_PATH.name
    instrucciones = {}
    for ins in (datos or {}).get("instrucciones") or []:
        iid = ins.get("id")
        if not _texto_ok(iid) or iid in instrucciones:
            errores.append(f"{donde}: cada instruccion necesita un 'id' unico")
            continue
        if ins.get("tipo") not in TIPOS:
            errores.append(f"{donde} > {iid}: 'tipo' debe ser uno de {', '.join(sorted(TIPOS))}")
            continue
        if list(ins.get("parametros") or []) != list(PARAMETROS[ins["tipo"]]):
            esperados = ", ".join(PARAMETROS[ins["tipo"]])
            errores.append(f"{donde} > {iid}: los parametros de '{ins['tipo']}' son {esperados}")
        for campo in ("etiqueta", "descripcion"):
            if not _texto_ok(ins.get(campo)):
                errores.append(f"{donde} > {iid}: falta '{campo}'")
        instrucciones[iid] = ins
    if not instrucciones:
        errores.append(f"{donde}: no hay instrucciones")
    return instrucciones


def _validar_nivel(nivel, nombre, instrucciones, errores):
    donde = f"niveles_codigo/{nombre}"
    if not _texto_ok(nivel.get("id")):
        errores.append(f"{donde}: falta 'id'")
    for campo in ("titulo", "objetivo"):
        if not _texto_ok(nivel.get(campo)):
            errores.append(f"{donde}: falta '{campo}'")
    variables = nivel.get("variables")
    if (
        not isinstance(variables, list)
        or not 1 <= len(variables) <= 4
        or len(set(variables)) != len(variables)
        or not all(_texto_ok(v) and len(v) <= 3 for v in variables)
    ):
        errores.append(f"{donde}: 'variables' debe tener de 1 a 4 nombres cortos sin repetir")
    bloques = nivel.get("bloques_disponibles")
    if not isinstance(bloques, list) or not bloques:
        errores.append(f"{donde}: 'bloques_disponibles' no puede estar vacio")
    else:
        for bloque in bloques:
            if bloque not in instrucciones:
                errores.append(
                    f"{donde}: el bloque '{bloque}' no existe en {INSTRUCCIONES_PATH.name}"
                )
    if not _entero(nivel.get("optimo"), 1):
        errores.append(f"{donde}: 'optimo' debe ser un entero mayor a 0")
    elif not _entero(nivel.get("max_bloques"), nivel["optimo"], MAX_BLOQUES_TABLERO):
        errores.append(f"{donde}: 'max_bloques' debe ir del optimo a {MAX_BLOQUES_TABLERO}")
    for clave, minimo in (("xp_base", 0), ("max_pasos", 1), ("orden", 0)):
        if not _entero(nivel.get(clave, 0), minimo):
            errores.append(f"{donde}: '{clave}' debe ser un entero de {minimo} en adelante")
    casos = nivel.get("casos")
    if not isinstance(casos, list) or not casos:
        errores.append(f"{donde}: necesita al menos un caso de prueba")
        return
    for caso in casos:
        listas = (caso.get("entradas"), caso.get("salida"))
        if not all(isinstance(lista, list) and lista for lista in listas) or not all(
            _entero(n, -999, 999) for lista in listas for n in lista
        ):
            errores.append(f"{donde}: cada caso necesita 'entradas' y 'salida' con enteros")


def _archivos():
    return [escenarios.CONFIG_PATH, INSTRUCCIONES_PATH, *sorted(NIVELES_DIR.glob("*.json"))]


def _firma():
    return tuple((str(r), r.stat().st_mtime_ns) for r in _archivos() if r.exists())


def _construir():
    errores = []
    config = _leer(escenarios.CONFIG_PATH, errores) or {}
    _validar_reglas(config, errores)
    instrucciones = _validar_instrucciones(_leer(INSTRUCCIONES_PATH, errores), errores)

    niveles = {}
    for ruta in sorted(NIVELES_DIR.glob("*.json")):
        nivel = _leer(ruta, errores)
        if nivel is None:
            continue
        antes = len(errores)
        _validar_nivel(nivel, ruta.name, instrucciones, errores)
        if nivel.get("id") in niveles:
            errores.append(f"niveles_codigo/{ruta.name}: id de nivel repetido")
        if len(errores) == antes:
            niveles[nivel["id"]] = nivel
    if not niveles and not errores:
        errores.append("No hay niveles en app/data/niveles_codigo/")
    orden = sorted(niveles.values(), key=lambda n: (n.get("orden", 0), n["id"]))
    catalogo = {
        "reglas": config.get("minijuego_codigo"),
        "instrucciones": instrucciones,
        "niveles": {n["id"]: n for n in orden},
    }
    return catalogo, errores


def validar():
    """Errores de las reglas, las instrucciones y los niveles (vacia si todo esta bien)."""
    return _construir()[1]


def cargar():
    """Devuelve {"reglas", "instrucciones", "niveles"}. Lanza escenarios.CatalogoError."""
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


# ---------------------------------------------------------------- tablero que manda el navegador
def _texto_corto(valor):
    return valor[:12] if isinstance(valor, str) else ""


def _leer_lista(lista, contexto, profundidad):
    if not isinstance(lista, list):
        raise TableroInvalido("El tablero no tiene un formato válido.")
    return [_leer_bloque(b, contexto, profundidad) for b in lista]


def _leer_bloque(datos, contexto, profundidad):
    nivel_, instrucciones, ids = contexto
    if not isinstance(datos, dict):
        raise TableroInvalido("El tablero no tiene un formato válido.")
    tipo = datos.get("tipo")
    if tipo not in nivel_["bloques_disponibles"]:
        raise TableroInvalido("Ese bloque no está disponible en este nivel.")
    bid = datos.get("id")
    if not _texto_ok(bid) or len(bid) > 24 or bid in ids:
        raise TableroInvalido("Cada bloque necesita un identificador único.")
    ids.add(bid)
    if len(ids) > MAX_BLOQUES_TABLERO:
        raise TableroInvalido("El tablero tiene demasiados bloques.")

    clase = instrucciones[tipo]["tipo"]
    bloque = {"id": bid, "tipo": tipo}
    if clase == "condicion":
        if profundidad >= MAX_PROFUNDIDAD:
            raise TableroInvalido("Hay demasiados SI uno dentro de otro.")
        condicion = datos.get("condicion") if isinstance(datos.get("condicion"), dict) else {}
        bloque["condicion"] = {c: _texto_corto(condicion.get(c)) for c in PARAMETROS[clase]}
        bloque["si"] = _leer_lista(datos.get("si", []), contexto, profundidad + 1)
        bloque["no"] = _leer_lista(datos.get("no", []), contexto, profundidad + 1)
    else:
        for campo in PARAMETROS[clase]:
            bloque[campo] = _texto_corto(datos.get(campo))
    return bloque


def leer_tablero(datos, nivel_, instrucciones):
    """Convierte {"tablero": [...], "sueltos": [...]} en bloques limpios (SDS 3.3.2)."""
    if not isinstance(datos, dict):
        raise TableroInvalido("El tablero no tiene un formato válido.")
    contexto = (nivel_, instrucciones, set())
    tablero = _leer_lista(datos.get("tablero", []), contexto, 0)
    sueltos = _leer_lista(datos.get("sueltos", []), contexto, 0)
    return tablero, sueltos


def contar(bloques):
    """Bloques usados (sin contar INICIO), incluidos los que estan dentro de un SI."""
    return sum(1 + contar(b.get("si", [])) + contar(b.get("no", [])) for b in bloques)


def huella(tablero):
    """Huella del tablero compilado: si cambia un solo bloque, cambia la huella (RN02)."""
    texto = json.dumps(tablero, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- compilar (RN02, FE1, FE3)
FRASES = {
    "variable": "elige la variable de cada bloque",
    "copia": "COPY TO necesita dos variables distintas",
    "comparacion": "el bloque SI necesita una comparación (por ejemplo A > B)",
    "rama": "la rama «se cumple» de un SI está vacía",
}


def _revisar(bloques, nivel_, instrucciones, errores):
    variables = nivel_["variables"]
    for b in bloques:
        clase = instrucciones[b["tipo"]]["tipo"]
        if clase == "entrada" and b["destino"] not in variables:
            errores.append((b["id"], "variable", "elige una variable"))
        elif clase == "salida" and b["valor"] not in variables:
            errores.append((b["id"], "variable", "elige una variable"))
        elif clase == "memoria" and (
            b["origen"] not in variables
            or b["destino"] not in variables
            or b["origen"] == b["destino"]
        ):
            errores.append((b["id"], "copia", "elige dos variables"))
        elif clase == "condicion":
            c = b["condicion"]
            if c["izq"] not in variables or c["der"] not in variables or c["op"] not in OPERADORES:
                errores.append((b["id"], "comparacion", "elige una comparación"))
            if not b["si"]:
                errores.append((b["id"], "rama", "su rama «se cumple» está vacía"))
            _revisar(b["si"], nivel_, instrucciones, errores)
            _revisar(b["no"], nivel_, instrucciones, errores)


def _unir(frases):
    if len(frases) > 1:
        frases = [", ".join(frases[:-1]), frases[-1]]
    texto = " y ".join(frases)
    return texto[:1].upper() + texto[1:] + "."


def revisar_tablero(tablero, sueltos, nivel_, instrucciones):
    """Valida sintaxis y conexiones sin ejecutar nada."""
    usados = contar(tablero) + contar(sueltos)
    base = {"bloques_usados": usados, "optimo": nivel_["optimo"], "errores": []}
    if usados == 0:  # FE3
        return {
            **base,
            "compilado": False,
            "vacio": True,
            "titulo": "El tablero está vacío",
            "mensaje": "Agrega bloques de instrucción antes de compilar.",
        }

    errores = []
    _revisar(tablero, nivel_, instrucciones, errores)
    errores += [(b["id"], "suelto", "no está conectado") for b in sueltos]

    claves = list(dict.fromkeys(clave for _, clave, _ in errores))
    frases = [FRASES[c] for c in claves if c in FRASES]
    if "suelto" in claves:
        cuantos = sum(1 for _, clave, _ in errores if clave == "suelto")
        frases.append(
            "hay un bloque sin conectar" if cuantos == 1 else f"hay {cuantos} bloques sin conectar"
        )
    if usados > nivel_["max_bloques"]:
        frases.append(f"usaste {usados} bloques y el límite del nivel es {nivel_['max_bloques']}")
    if not tablero and not frases:
        frases.append("conecta los bloques debajo de INICIO")

    ok = not frases
    return {
        **base,
        "compilado": ok,
        "vacio": False,
        "errores": [{"bloque_id": bid, "mensaje": nota} for bid, _, nota in errores],
        "titulo": "Todo conectado" if ok else "No se pudo compilar",
        "mensaje": "Tu algoritmo está listo. Presiona EJECUTAR para probarlo."
        if ok
        else _unir(frases),
    }


# ---------------------------------------------------------------- interprete (FE2)
class _Alto(Exception):
    """La ejecucion se detiene: dato equivocado, instruccion imposible o demasiados pasos."""

    def __init__(self, bloque_id, nota, mensaje, caja_mal=False):
        super().__init__(mensaje)
        self.fallo = {
            "bloque_id": bloque_id,
            "nota": nota,
            "mensaje": mensaje,
            "caja_mal": caja_mal,
        }


def _registrar(estado, bloque, nota):
    if len(estado["traza"]) >= estado["max_pasos"]:
        raise _Alto(
            bloque["id"],
            "demasiados pasos",
            "El algoritmo dio demasiados pasos sin terminar.",
        )
    estado["traza"].append(
        {
            "bloque_id": bloque["id"],
            "inbox": list(estado["inbox"]),
            "outbox": list(estado["outbox"]),
            "variables": dict(estado["variables"]),
            "nota": nota,
        }
    )


def _valor(estado, bloque, variable):
    valor = estado["variables"].get(variable)
    if valor is None:
        raise _Alto(
            bloque["id"],
            f"{variable} no tiene valor",
            f"{variable} todavía no tiene valor: léelo de la INBOX antes de usarlo.",
        )
    return valor


def _paso(bloque, estado, sis):
    clase = estado["instrucciones"][bloque["tipo"]]["tipo"]
    esperada = estado["esperada"]
    if clase == "entrada":
        if not estado["inbox"]:
            raise _Alto(
                bloque["id"],
                "la INBOX está vacía",
                "Intentaste leer de la INBOX, pero ya no quedan datos.",
            )
        valor = estado["inbox"].pop(0)
        estado["variables"][bloque["destino"]] = valor
        _registrar(estado, bloque, f"Entra {valor} → {bloque['destino']}")
    elif clase == "memoria":
        valor = _valor(estado, bloque, bloque["origen"])
        estado["variables"][bloque["destino"]] = valor
        _registrar(estado, bloque, f"{bloque['destino']} = {bloque['origen']} → {valor}")
    elif clase == "salida":
        valor = _valor(estado, bloque, bloque["valor"])
        estado["outbox"].append(valor)
        _registrar(estado, bloque, f"Se entrega {bloque['valor']} ({valor})")
        posicion = len(estado["outbox"]) - 1
        if posicion >= len(esperada):
            raise _Alto(
                bloque["id"],
                "sobra este dato",
                f"Llegó {valor} a la OUTBOX, pero ya no se esperaban más datos.",
                caja_mal=True,
            )
        if valor != esperada[posicion]:
            # Si la salida dependía de una condición, lo más probable es que el error esté ahí
            if sis:
                marca, nota = sis[-1], "revisa esta condición"
            else:
                marca, nota = bloque["id"], "revisa este bloque"
            raise _Alto(
                marca, nota, f"Se esperaba {esperada[posicion]} y llegó {valor}.", caja_mal=True
            )
    else:  # condicion
        c = bloque["condicion"]
        izq, der = _valor(estado, bloque, c["izq"]), _valor(estado, bloque, c["der"])
        funcion, simbolo = OPERADORES[c["op"]]
        cumple = funcion(izq, der)
        rama = "se cumple" if cumple else "no se cumple"
        nota = f"¿{izq} {simbolo} {der}? {'Sí' if cumple else 'No'} → rama «{rama}»"
        _registrar(estado, bloque, nota)
        _correr(bloque["si"] if cumple else bloque["no"], estado, (*sis, bloque["id"]))


def _correr(bloques, estado, sis=()):
    for bloque in bloques:
        _paso(bloque, estado, sis)


def _probar(tablero, nivel_, instrucciones, caso, numero):
    estado = {
        "instrucciones": instrucciones,
        "variables": {v: None for v in nivel_["variables"]},
        "inbox": list(caso["entradas"]),
        "outbox": [],
        "esperada": caso["salida"],
        "traza": [],
        "max_pasos": nivel_["max_pasos"],
    }
    fallo = None
    try:
        _correr(tablero, estado)
    except _Alto as alto:
        fallo = alto.fallo
    if fallo is None and estado["outbox"] != caso["salida"]:
        falta = caso["salida"][len(estado["outbox"])]
        fallo = {
            "bloque_id": None,
            "nota": None,
            "mensaje": f"Se esperaba {falta} en la OUTBOX y no llegó nada.",
            "caja_mal": False,
        }
    return {
        "numero": numero,
        "correcta": fallo is None,
        "entradas": caso["entradas"],
        "salida_esperada": caso["salida"],
        "salida": estado["outbox"],
        "traza": estado["traza"],
        "fallo": fallo,
    }


def correr_casos(tablero, nivel_, instrucciones):
    """Simula INBOX -> logica -> OUTBOX con cada caso de prueba del nivel.

    Para animar se manda el primer caso que falla o, si todos pasan, el ejemplo (caso 1).
    De los demas casos solo viaja si pasaron, no sus datos.
    """
    resultados = [
        _probar(tablero, nivel_, instrucciones, caso, i + 1)
        for i, caso in enumerate(nivel_["casos"])
    ]
    fallido = next((r for r in resultados if not r["correcta"]), None)
    return {
        "correcta": fallido is None,
        "caso": fallido or resultados[0],
        "casos": [{"numero": r["numero"], "correcta": r["correcta"]} for r in resultados],
    }


# ---------------------------------------------------------------- calificar (RN01, RN03-RN05)
def penalizacion(fallos, reglas):
    return min(reglas["penalizacion_maxima"], fallos * reglas["penalizacion_por_fallo"])


def calificar(usados, fallos, nivel_, reglas):
    """Estrellas segun bloques usados contra el optimo y XP con penalizacion por fallos."""
    extra = max(0, usados - nivel_["optimo"])
    regla = next(
        r
        for r in reglas["estrellas"]
        if r["bloques_extra_max"] is None or extra <= r["bloques_extra_max"]
    )
    castigo = penalizacion(fallos, reglas)
    base = round(nivel_["xp_base"] * regla["porcentaje_xp"] / 100)
    return {
        "estrellas": regla["estrellas"],
        "estrellas_max": max(r["estrellas"] for r in reglas["estrellas"]),
        "bloques_usados": usados,
        "optimo": nivel_["optimo"],
        "xp_base": base,
        "porcentaje_xp": regla["porcentaje_xp"],
        "intentos_fallidos": fallos,
        "penalizacion": castigo,
        "xp": round(base * (100 - castigo) / 100),
    }


# ---------------------------------------------------------------- intentos del jugador
def _de_jugador(jugador):
    return IntentoCodigo.objects.filter(**jugador.filtro())


def nivel_para(jugador):
    """Nivel con el que abre el modo: el primero que el jugador no ha resuelto."""
    niveles = list(cargar()["niveles"])
    resueltos = set(
        _de_jugador(jugador)
        .filter(estado=IntentoCodigo.RESUELTO)
        .values_list("nivel_id", flat=True)
    )
    return next((n for n in niveles if n not in resueltos), niveles[0])


def resumen_jugador(jugador):
    """Para la tarjeta del menu de modos: niveles resueltos y mejores estrellas."""
    catalogo = cargar()
    mejores = {}
    for nivel_id, estrellas in (
        _de_jugador(jugador)
        .filter(estado=IntentoCodigo.RESUELTO)
        .values_list("nivel_id", "estrellas")
    ):
        mejores[nivel_id] = max(mejores.get(nivel_id, 0), estrellas or 0)
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

    Recargar la pagina devuelve el mismo intento con su ultimo tablero compilado. Si el ultimo
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


def estado_publico(intento):
    """Lo que necesita la mesa de trabajo (minijuego_codigo.html). Sin las salidas ocultas."""
    catalogo = cargar()
    nivel_ = catalogo["niveles"][intento.nivel_id]
    reglas = catalogo["reglas"]
    return {
        "intento_id": str(intento.id),
        "estado": intento.estado,
        "nivel": {
            "id": nivel_["id"],
            "titulo": nivel_["titulo"],
            "objetivo": nivel_["objetivo"],
            "variables": nivel_["variables"],
            "bloques": [
                {
                    k: catalogo["instrucciones"][b][k]
                    for k in ("id", "etiqueta", "tipo", "descripcion")
                }
                for b in nivel_["bloques_disponibles"]
            ],
            "operadores": [{"id": k, "simbolo": v[1]} for k, v in OPERADORES.items()],
            "optimo": nivel_["optimo"],
            "max_bloques": nivel_["max_bloques"],
            "xp_base": nivel_["xp_base"],
            "ejemplo": {
                "entradas": nivel_["casos"][0]["entradas"],
                "salida": nivel_["casos"][0]["salida"],
            },
        },
        "tablero": intento.tablero,
        "compilado": bool(intento.huella),
        "intentos_fallidos": intento.intentos_fallidos,
        "penalizacion": penalizacion(intento.intentos_fallidos, reglas),
        "penalizacion_por_fallo": reglas["penalizacion_por_fallo"],
        "penalizacion_maxima": reglas["penalizacion_maxima"],
        "resultado": intento.resultado if intento.estado == IntentoCodigo.RESUELTO else None,
    }


def compilar(intento, datos):
    """Pasos 4 y 5. Compilar no cuenta como intento fallido."""
    catalogo, nivel_ = _en_curso(intento)
    tablero, sueltos = leer_tablero(datos, nivel_, catalogo["instrucciones"])
    resultado = revisar_tablero(tablero, sueltos, nivel_, catalogo["instrucciones"])
    if resultado["compilado"]:
        intento.tablero = tablero
        intento.huella = huella(tablero)
        intento.bloques_usados = resultado["bloques_usados"]
    else:
        intento.huella = ""  # lo que estaba compilado ya no es lo que hay en el tablero
    intento.save(update_fields=["tablero", "huella", "bloques_usados", "actualizado"])
    return resultado


def ejecutar(intento, datos):
    """Pasos 6 a 9: corre el tablero compilado con todos los casos y califica."""
    catalogo, nivel_ = _en_curso(intento)
    tablero, sueltos = leer_tablero(datos, nivel_, catalogo["instrucciones"])
    if sueltos or not intento.huella or huella(tablero) != intento.huella:
        raise ReglaCodigo("Vuelve a compilar el tablero: solo se ejecuta el tablero compilado.")

    reglas = catalogo["reglas"]
    prueba = correr_casos(tablero, nivel_, catalogo["instrucciones"])
    calificacion = None
    if not prueba["correcta"]:  # FE2
        intento.intentos_fallidos += 1  # RN05
        intento.save(update_fields=["intentos_fallidos", "actualizado"])
    else:
        calificacion = calificar(contar(tablero), intento.intentos_fallidos, nivel_, reglas)
        intento.estado = IntentoCodigo.RESUELTO
        intento.estrellas = calificacion["estrellas"]
        intento.xp_obtenida = calificacion["xp"]
        intento.resultado = calificacion
        intento.save()
    return {
        **prueba,
        "resultado": calificacion,
        "intentos_fallidos": intento.intentos_fallidos,
        "penalizacion": penalizacion(intento.intentos_fallidos, reglas),
    }


def salir(intento):
    """FA3: se pierde la solucion y no se gana XP. Un intento ya resuelto no cambia."""
    if intento.estado == IntentoCodigo.EN_CURSO:
        intento.estado = IntentoCodigo.ABANDONADO
        intento.save(update_fields=["estado", "actualizado"])
    return intento
