"""CU04 - Resolver minijuego de código: se abre desde el menú de modos (CU05).

SDS 1.3.4 y 3.3.2; reglas CU04-RN01 a RN05. Cubre el contenido (niveles e instrucciones), el
compilador, el intérprete, la calificación y la API de la mesa de trabajo.
"""

import copy
import json

import pytest
from django.core.management import call_command

from app.models import IntentoCodigo
from app.services import minijuego_codigo

MESA = "/jugar/codigo/comparador/"


def _b(n, tipo, **campos):
    return {"id": f"b{n}", "tipo": tipo, **campos}


def _si(n, izq, op, der, si, no):
    return _b(n, "SI", condicion={"izq": izq, "op": op, "der": der}, si=si, no=no)


# INBOX → A, INBOX → B, SI A > B: OUTBOX A / SI NO: OUTBOX B  (5 bloques = óptimo)
CORRECTO = {
    "tablero": [
        _b(1, "INBOX", destino="A"),
        _b(2, "INBOX", destino="B"),
        _si(3, "A", ">", "B", [_b(4, "OUTBOX", valor="A")], [_b(5, "OUTBOX", valor="B")]),
    ],
    "sueltos": [],
}


def _tablero(**condicion):
    tablero = copy.deepcopy(CORRECTO)
    tablero["tablero"][2]["condicion"].update(condicion)
    return tablero


def _catalogo():
    catalogo = minijuego_codigo.cargar()
    return catalogo["niveles"]["comparador"], catalogo["instrucciones"]


def _revisar(datos):
    nivel, instrucciones = _catalogo()
    tablero, sueltos = minijuego_codigo.leer_tablero(datos, nivel, instrucciones)
    return minijuego_codigo.revisar_tablero(tablero, sueltos, nivel, instrucciones)


def _correr(datos):
    nivel, instrucciones = _catalogo()
    tablero, _ = minijuego_codigo.leer_tablero(datos, nivel, instrucciones)
    return minijuego_codigo.correr_casos(tablero, nivel, instrucciones)


def _abrir(client, url=MESA):
    assert client.get(url).status_code == 200
    return IntentoCodigo.objects.latest("creado")


def _post(client, intento, accion, datos=None):
    url = f"/api/codigo/{intento.id}/{accion}/"
    return client.post(url, json.dumps(datos or {}), content_type="application/json")


def _compilar_y_ejecutar(client, intento, datos):
    assert _post(client, intento, "compilar", datos).json()["codigo"]["compilado"]
    return _post(client, intento, "ejecutar", datos).json()["codigo"]


# ---------------------------------------------------------------- contenido (RNF-MAN-05, 07)
def test_niveles_e_instrucciones_son_validos():
    assert minijuego_codigo.validar() == []
    nivel, instrucciones = _catalogo()
    assert set(nivel["bloques_disponibles"]) == {"INBOX", "OUTBOX", "COPY_TO", "SI"}
    assert nivel["optimo"] == 5 and nivel["casos"][0] == {"entradas": [3, 8], "salida": [8]}
    assert {i["tipo"] for i in instrucciones.values()} == {
        "entrada",
        "salida",
        "memoria",
        "condicion",
    }


def test_validar_escenarios_revisa_el_minijuego(capsys):
    call_command("validar_escenarios")
    assert "Minijuego de código válido: 1 nivel(es) y 4 instrucciones" in capsys.readouterr().out


# ---------------------------------------------------------------- menú de modos y pasos 1 a 3
@pytest.mark.django_db
def test_el_menu_de_modos_abre_el_minijuego(client):
    html = client.get("/jugar/").content.decode()
    assert 'href="/jugar/codigo/"' in html and "En desarrollo" not in html
    respuesta = client.get("/jugar/codigo/")
    assert respuesta.status_code == 302 and respuesta["Location"] == MESA


@pytest.mark.django_db
def test_la_mesa_de_trabajo_carga_el_nivel(client):
    html = client.get(MESA).content.decode()
    assert "El Comparador" in html and 'id="mj-ayuda"' in html
    assert "css/taller.css" in html and "css/minijuego_codigo.css" in html
    assert "js/minijuego_codigo.js" in html
    assert client.get("/jugar/codigo/no-existe/").status_code == 404


@pytest.mark.django_db
def test_recargar_retoma_el_mismo_intento_con_su_tablero(client):
    intento = _abrir(client)
    _post(client, intento, "compilar", CORRECTO)
    assert _abrir(client).id == intento.id
    assert IntentoCodigo.objects.count() == 1
    assert '"compilado": true' in client.get(MESA).content.decode()


# ---------------------------------------------------------------- compilar (RN02, FE1, FE3)
def test_fe3_tablero_vacio():
    r = _revisar({"tablero": [], "sueltos": []})
    assert r["vacio"] and not r["compilado"] and r["titulo"] == "El tablero está vacío"


def test_fe1_si_sin_comparacion_y_bloque_suelto():
    datos = _tablero(izq="", op="")
    datos["tablero"][2]["no"] = []
    datos["sueltos"] = [_b(9, "OUTBOX", valor="B")]
    r = _revisar(datos)
    assert not r["compilado"]
    assert {e["bloque_id"]: e["mensaje"] for e in r["errores"]} == {
        "b3": "elige una comparación",
        "b9": "no está conectado",
    }
    assert "comparación" in r["mensaje"] and "sin conectar" in r["mensaje"]


def test_compilacion_correcta_cuenta_bloques():
    r = _revisar(CORRECTO)
    assert r["compilado"] and r["bloques_usados"] == 5 and r["titulo"] == "Todo conectado"


@pytest.mark.django_db
def test_tablero_mal_formado_se_rechaza(client):
    intento = _abrir(client)
    otro_bloque = {"tablero": [{"id": "x", "tipo": "BORRAR_TODO"}]}
    assert _post(client, intento, "compilar", otro_bloque).status_code == 400
    repetidos = {"tablero": [_b(1, "INBOX", destino="A"), _b(1, "OUTBOX", valor="A")]}
    assert _post(client, intento, "compilar", repetidos).status_code == 400


# ---------------------------------------------------------------- ejecutar (RN02, FE2)
@pytest.mark.django_db
def test_rn02_solo_se_ejecuta_el_tablero_compilado(client):
    intento = _abrir(client)
    assert _post(client, intento, "ejecutar", CORRECTO).status_code == 409  # sin compilar
    _post(client, intento, "compilar", CORRECTO)
    cambiado = _tablero(op="<")
    assert _post(client, intento, "ejecutar", cambiado).status_code == 409  # FA2
    intento.refresh_from_db()
    assert intento.intentos_fallidos == 0  # rechazar no cuenta como prueba fallida


def test_ejecucion_correcta_pasa_todos_los_casos():
    r = _correr(CORRECTO)
    assert r["correcta"] and [c["correcta"] for c in r["casos"]] == [True, True, True]
    paso = r["caso"]["traza"][2]
    assert paso["bloque_id"] == "b3" and paso["nota"] == "¿3 > 8? No → rama «no se cumple»"
    assert paso["inbox"] == [] and paso["variables"] == {"A": 3, "B": 8}
    assert r["caso"]["salida"] == [8]


def test_fe2_salida_incorrecta_senala_la_condicion():
    r = _correr(_tablero(op="<"))
    fallo = r["caso"]["fallo"]
    assert not r["correcta"] and r["caso"]["salida"] == [3]
    assert fallo["bloque_id"] == "b3" and fallo["nota"] == "revisa esta condición"
    assert fallo["mensaje"] == "Se esperaba 8 y llegó 3." and fallo["caja_mal"]


def test_los_casos_ocultos_evitan_soluciones_a_la_medida_del_ejemplo():
    siempre_b = {
        "tablero": [
            _b(1, "INBOX", destino="A"),
            _b(2, "INBOX", destino="B"),
            _b(3, "OUTBOX", valor="B"),
        ]
    }
    r = _correr(siempre_b)
    assert not r["correcta"] and r["caso"]["numero"] == 2 and r["caso"]["entradas"] == [9, 2]


def test_usar_una_variable_sin_valor_detiene_la_ejecucion():
    r = _correr({"tablero": [_b(1, "OUTBOX", valor="A")]})
    assert r["caso"]["fallo"]["bloque_id"] == "b1"
    assert r["caso"]["fallo"]["nota"] == "A no tiene valor"


def test_copy_to_copia_una_variable_en_otra():
    datos = {
        "tablero": [
            _b(1, "INBOX", destino="A"),
            _b(2, "INBOX", destino="B"),
            _si(3, "B", ">", "A", [_b(4, "COPY_TO", origen="B", destino="A")], []),
            _b(5, "OUTBOX", valor="A"),
        ]
    }
    assert _correr(datos)["correcta"]


# ---------------------------------------------------------------- calificar (RN01, RN03 a RN05)
@pytest.mark.parametrize(
    "bloques, fallos, estrellas, xp",
    [
        (5, 0, 3, 40),  # óptimo: 100% de la XP base
        (5, 1, 3, 38),  # RN05: −5% por prueba fallida
        (7, 0, 2, 30),  # 2 bloques de más: 75%
        (9, 0, 1, 20),  # más de 2 de más: 50%
        (5, 30, 3, 20),  # la penalización se detiene en −50%
    ],
)
def test_estrellas_y_xp(bloques, fallos, estrellas, xp):
    nivel, _ = _catalogo()
    r = minijuego_codigo.calificar(bloques, fallos, nivel, minijuego_codigo.cargar()["reglas"])
    assert (r["estrellas"], r["xp"]) == (estrellas, xp)


# ---------------------------------------------------------------- flujo completo por la API
@pytest.mark.django_db
def test_flujo_normal_resolver_y_volver_al_menu(client):
    intento = _abrir(client)
    r = _compilar_y_ejecutar(client, intento, CORRECTO)
    assert r["correcta"] and r["resultado"]["estrellas"] == 3 and r["resultado"]["xp"] == 40

    intento.refresh_from_db()
    assert intento.estado == IntentoCodigo.RESUELTO
    assert (intento.estrellas, intento.xp_obtenida, intento.bloques_usados) == (3, 40, 5)
    # Ya resuelto no se vuelve a cobrar XP
    assert _post(client, intento, "ejecutar", CORRECTO).status_code == 409
    # El menú muestra las estrellas ganadas
    assert "⭐ 3 de 3 estrellas" in client.get("/jugar/").content.decode()


@pytest.mark.django_db
def test_fe2_cada_prueba_fallida_resta_xp(client):
    intento = _abrir(client)
    r = _compilar_y_ejecutar(client, intento, _tablero(op="<"))
    assert not r["correcta"] and r["intentos_fallidos"] == 1 and r["penalizacion"] == 5
    r = _compilar_y_ejecutar(client, intento, CORRECTO)
    assert r["resultado"]["xp"] == 38
    intento.refresh_from_db()
    assert intento.intentos_fallidos == 1 and intento.xp_obtenida == 38


@pytest.mark.django_db
def test_fa3_salir_regresa_al_menu_sin_xp(client):
    intento = _abrir(client)
    respuesta = _post(client, intento, "salir")
    assert respuesta.json()["codigo"]["url"] == "/jugar/"
    intento.refresh_from_db()
    assert intento.estado == IntentoCodigo.ABANDONADO and intento.xp_obtenida == 0
    assert _post(client, intento, "compilar", CORRECTO).status_code == 409
    # Al volver a entrar empieza un intento nuevo
    assert _abrir(client).id != intento.id


@pytest.mark.django_db
def test_jugar_otra_vez_abre_un_intento_nuevo(client):
    intento = _abrir(client)
    _compilar_y_ejecutar(client, intento, CORRECTO)
    assert _abrir(client).id == intento.id  # sin «otra vez» se ve el resultado
    nuevo = _abrir(client, MESA + "?nuevo=1")
    assert nuevo.id != intento.id and nuevo.estado == IntentoCodigo.EN_CURSO


@pytest.mark.django_db
def test_el_intento_es_solo_de_su_jugador(client, django_user_model):
    intento = _abrir(client)
    otro = django_user_model.objects.create_user("otro", password="x")
    client.force_login(otro)
    assert _post(client, intento, "compilar", CORRECTO).status_code == 404
