"""CU04 - Resolver minijuego de código: se abre desde el menú de modos (CU05).

SDS 1.3.4 y 3.3.2; reglas CU04-RN01 a RN05. Cada nivel es un programa en Python o pseudocódigo
con sus líneas revueltas. Cubre el contenido (niveles), la revisión del acomodo (varias
soluciones válidas, sangría, orden, distractores), la calificación y la API de la mesa.
"""

import json

import pytest
from django.core.management import call_command

from app.models import IntentoCodigo
from app.services import minijuego_codigo

AREA = "area-rectangulo-python"
MAYOR = "mayor-de-dos-python"
MAYOR_PSEUDO = "mayor-de-dos-pseudocodigo"
SUMA = "suma-hasta-n-python"
MESA = f"/jugar/codigo/{AREA}/"


def _nivel(nivel_id):
    return minijuego_codigo.cargar()["niveles"][nivel_id]


def _p(*lineas):
    """_p(("l1", 0), ("l2", 1)) -> [{"id": "l1", "sangria": 0}, ...]"""
    return [{"id": lid, "sangria": sangria} for lid, sangria in lineas]


def _solucion(nivel_id):
    return [{"id": ln["id"], "sangria": ln["sangria"]} for ln in _nivel(nivel_id)["lineas"]]


def _revisar(nivel_id, programa):
    return minijuego_codigo.revisar_programa(programa, _nivel(nivel_id))


def _notas(revision):
    return {e["linea_id"]: e["nota"] for e in revision["errores"]}


def _abrir(client, url=MESA):
    assert client.get(url).status_code == 200
    return IntentoCodigo.objects.latest("creado")


def _comprobar(client, intento, programa):
    url = f"/api/codigo/{intento.id}/comprobar/"
    return client.post(url, json.dumps({"programa": programa}), content_type="application/json")


def _estado(client, url=MESA):
    html = client.get(url).content.decode()
    inicio = html.index('id="mj-estado"')
    return json.loads(html[html.index(">", inicio) + 1 : html.index("</script>", inicio)])


# ---------------------------------------------------------------- contenido (RNF-MAN-05, 07)
def test_los_niveles_son_validos_en_los_dos_lenguajes():
    assert minijuego_codigo.validar() == []
    catalogo = minijuego_codigo.cargar()
    assert catalogo["programas"] == 4 and len(catalogo["niveles"]) == 8
    for lenguaje in ("python", "pseudocodigo"):
        niveles = minijuego_codigo.niveles_de(lenguaje)
        assert [n["programa"] for n in niveles] == [
            "area-rectangulo",
            "mayor-de-dos",
            "suma-hasta-n",
            "contar-positivos",
        ]
        # Los distractores aparecen desde el nivel 3
        assert [len(n["distractores"]) for n in niveles] == [0, 0, 1, 2]


def test_validar_escenarios_revisa_el_minijuego(capsys):
    call_command("validar_escenarios")
    salida = capsys.readouterr().out
    assert "Minijuego de código válido: 4 programa(s) en 2 lenguaje(s), 8 niveles." in salida


def test_el_validador_detecta_reglas_que_no_cumple_su_propia_solucion():
    datos = {
        "id": "prueba",
        "titulo": "Prueba",
        "objetivo": "Probar",
        "xp_base": 10,
        "lenguajes": {
            "python": {
                "lineas": [
                    {"id": "l1", "codigo": "x = 1", "sangria": 0, "despues_de": ["l2"]},
                    {"id": "l2", "codigo": "print(x)", "sangria": 0},
                ],
                "consola": [{"texto": "1"}],
            }
        },
    }
    errores = []
    assert minijuego_codigo._validar_nivel(datos, "prueba.json", errores) == []
    assert "no cumplen sus reglas" in errores[0]

    datos["lenguajes"]["python"]["lineas"][0] = {"id": "l1", "codigo": "print(x)", "sangria": 0}
    errores = []
    minijuego_codigo._validar_nivel(datos, "prueba.json", errores)
    assert any("se repite" in e for e in errores)


# ---------------------------------------------------------------- varias soluciones válidas
def test_la_solucion_de_cada_nivel_es_correcta():
    for nivel_id in minijuego_codigo.cargar()["niveles"]:
        assert _revisar(nivel_id, _solucion(nivel_id))["correcta"], nivel_id


def test_los_datos_se_pueden_leer_en_cualquier_orden():
    # Python: altura antes que base
    assert _revisar(AREA, _p(("l2", 0), ("l1", 0), ("l3", 0), ("l4", 0)))["correcta"]
    # Pseudocódigo: Leer b antes que Leer a
    otro_orden = _p(
        ("l1", 0),
        ("l3", 1),
        ("l2", 1),
        ("l4", 1),
        ("l5", 2),
        ("l6", 1),
        ("l7", 2),
        ("l8", 1),
        ("l9", 0),
    )
    assert _revisar(MAYOR_PSEUDO, otro_orden)["correcta"]
    # Suma: inicializar la suma antes de leer N
    assert _revisar(SUMA, _p(("l2", 0), ("l1", 0), ("l3", 0), ("l4", 1), ("l5", 0)))["correcta"]


# ---------------------------------------------------------------- FE1 y FE3: no se califica
def test_fe3_programa_vacio():
    r = _revisar(AREA, [])
    assert r["vacio"] and not r["completo"] and r["titulo"] == "El programa está vacío"


def test_fe1_faltan_lineas():
    r = _revisar(AREA, _p(("l1", 0), ("l2", 0)))
    assert not r["completo"] and r["faltan"] == 2
    assert r["mensaje"] == "Todavía quedan 2 líneas del programa en el banco."


# ---------------------------------------------------------------- FE2: reglas que no se cumplen
def test_fe2_una_operacion_antes_de_sus_datos():
    r = _revisar(AREA, _p(("l1", 0), ("l3", 0), ("l2", 0), ("l4", 0)))
    assert r["completo"] and not r["correcta"]
    assert _notas(r) == {"l3": "está demasiado arriba"}
    assert (
        r["mensaje"]
        == '«area = base * altura» debe ir después de «altura = float(input("Altura: "))».'
    )


def test_fe2_sangria_que_falta_y_sangria_de_mas():
    sin_sangria = _p(("l1", 0), ("l2", 0), ("l3", 0), ("l4", 0), ("l5", 0), ("l6", 1))
    r = _revisar(MAYOR, sin_sangria)
    assert _notas(r)["l4"] == "dale sangría"
    assert r["mensaje"] == '«print("El mayor es", a)» debe ir dentro de «if a > b:»: dale sangría.'

    dentro_de_otra = _p(("l1", 0), ("l2", 1), ("l3", 0), ("l4", 1), ("l5", 0), ("l6", 1))
    assert _notas(_revisar(MAYOR, dentro_de_otra)) == {"l2": "quítale sangría"}
    de_mas = _p(("l1", 0), ("l2", 2), ("l3", 0), ("l4", 1), ("l5", 0), ("l6", 1))
    assert _notas(_revisar(MAYOR, de_mas)) == {"l2": "sangría de más"}


def test_fe2_else_debe_ir_despues_del_bloque_del_if():
    # else entre el if y lo que tiene adentro: lo de adentro queda en el else
    r = _revisar(MAYOR, _p(("l1", 0), ("l2", 0), ("l3", 0), ("l5", 0), ("l4", 1), ("l6", 1)))
    assert not r["correcta"] and "l4" in _notas(r)
    # else antes del if
    r = _revisar(MAYOR, _p(("l1", 0), ("l2", 0), ("l5", 0), ("l6", 1), ("l3", 0), ("l4", 1)))
    assert _notas(r)["l5"] == "va justo después de otro bloque"


def test_fe2_fin_si_antes_de_tiempo_en_pseudocodigo():
    # FinSi antes del SiNo
    programa = _p(
        ("l1", 0),
        ("l2", 1),
        ("l3", 1),
        ("l4", 1),
        ("l5", 2),
        ("l8", 1),
        ("l6", 1),
        ("l7", 2),
        ("l9", 0),
    )
    r = _revisar(MAYOR_PSEUDO, programa)
    assert not r["correcta"] and {"l8", "l6"} & set(_notas(r))


def test_fe2_un_distractor_no_va_en_el_programa():
    con_distractor = _p(("l1", 0), ("l2", 0), ("l3", 0), ("l4", 1), ("d1", 1), ("l5", 0))
    r = _revisar(SUMA, con_distractor)
    assert _notas(r) == {"d1": "esta línea sobra"}
    assert (
        r["mensaje"] == "«for i in range(1, n):» no forma parte de la solución: regrésala al banco."
    )
    # Usar el distractor en lugar de la línea buena deja el programa incompleto
    cambiado = _p(("l1", 0), ("l2", 0), ("d1", 0), ("l4", 1), ("l5", 0))
    assert not _revisar(SUMA, cambiado)["completo"]


# ---------------------------------------------------------------- calificar (RN01, RN03 a RN05)
@pytest.mark.parametrize(
    "fallos, estrellas, xp",
    [
        (0, 3, 40),  # a la primera: 100% de la XP base
        (1, 2, 28),  # 75% de 40 = 30, menos 5% por el fallo (RN05)
        (2, 2, 27),  # 30 menos 10%
        (3, 1, 17),  # 50% de 40 = 20, menos 15%
        (30, 1, 10),  # la penalización se detiene en −50%
    ],
)
def test_estrellas_y_xp(fallos, estrellas, xp):
    r = minijuego_codigo.calificar(fallos, _nivel(MAYOR), minijuego_codigo.cargar()["reglas"])
    assert (r["estrellas"], r["xp"]) == (estrellas, xp)


# ---------------------------------------------------------------- menú de modos y pasos 1 a 3
@pytest.mark.django_db
def test_el_menu_de_modos_abre_el_minijuego(client):
    html = client.get("/jugar/").content.decode()
    assert 'href="/jugar/codigo/"' in html and "Pseudocódigo" in html
    respuesta = client.get("/jugar/codigo/")
    assert respuesta.status_code == 302 and respuesta["Location"] == MESA
    respuesta = client.get("/jugar/codigo/?lenguaje=pseudocodigo")
    assert respuesta["Location"] == "/jugar/codigo/area-rectangulo-pseudocodigo/"


@pytest.mark.django_db
def test_se_recuerda_el_ultimo_lenguaje(client):
    _abrir(client, "/jugar/codigo/suma-hasta-n-pseudocodigo/")
    assert client.get("/jugar/codigo/")["Location"] == "/jugar/codigo/area-rectangulo-pseudocodigo/"


@pytest.mark.django_db
def test_la_mesa_de_trabajo_carga_el_nivel_sin_sus_reglas(client):
    html = client.get(MESA).content.decode()
    assert "Área de un rectángulo" in html and 'id="mj-ayuda"' in html
    assert "css/taller.css" in html and "js/minijuego_codigo.js" in html
    assert client.get("/jugar/codigo/no-existe/").status_code == 404

    estado = _estado(client)
    lineas = estado["nivel"]["lineas"]
    assert all(set(ln) == {"id", "codigo"} for ln in lineas)  # sin sangría, padre ni orden
    assert [ln["id"] for ln in lineas] != [
        "l1",
        "l2",
        "l3",
        "l4",
    ]  # nunca en el orden de la solución
    assert _estado(client)["nivel"]["lineas"] == lineas  # el mismo revuelto al recargar
    assert [n["id"] for n in estado["niveles"]][0] == AREA and len(estado["niveles"]) == 4
    otro = {ln["id"]: ln["nivel_id"] for ln in estado["lenguajes"]}
    assert otro == {"python": AREA, "pseudocodigo": "area-rectangulo-pseudocodigo"}


@pytest.mark.django_db
def test_programa_mal_formado_se_rechaza(client):
    intento = _abrir(client)
    assert _comprobar(client, intento, _p(("x9", 0))).status_code == 400
    assert _comprobar(client, intento, _p(("l1", 0), ("l1", 0))).status_code == 400
    assert _comprobar(client, intento, _p(("l1", 9))).status_code == 400
    url = f"/api/codigo/{intento.id}/comprobar/"
    assert client.post(url, "{}", content_type="application/json").status_code == 400


# ---------------------------------------------------------------- flujo completo por la API
@pytest.mark.django_db
def test_incompleto_no_cuenta_como_intento_fallido(client):
    intento = _abrir(client)
    r = _comprobar(client, intento, _p(("l1", 0))).json()["codigo"]
    assert not r["completo"] and r["intentos_fallidos"] == 0


@pytest.mark.django_db
def test_rn02_el_mismo_acomodo_no_se_cobra_dos_veces(client):
    intento = _abrir(client)
    mal = _p(("l1", 0), ("l3", 0), ("l2", 0), ("l4", 0))
    r = _comprobar(client, intento, mal).json()["codigo"]
    assert not r["correcta"] and r["intentos_fallidos"] == 1 and not r["repetido"]
    r = _comprobar(client, intento, mal).json()["codigo"]
    assert r["repetido"] and r["intentos_fallidos"] == 1
    otro_mal = _p(("l4", 0), ("l1", 0), ("l2", 0), ("l3", 0))
    assert _comprobar(client, intento, otro_mal).json()["codigo"]["intentos_fallidos"] == 2


@pytest.mark.django_db
def test_flujo_normal_resolver_y_volver_al_menu(client):
    intento = _abrir(client)
    _comprobar(client, intento, _p(("l1", 0), ("l3", 0), ("l2", 0), ("l4", 0)))  # 1 fallo
    r = _comprobar(client, intento, _p(("l2", 0), ("l1", 0), ("l3", 0), ("l4", 0))).json()["codigo"]
    assert r["correcta"] and r["resultado"]["estrellas"] == 2 and r["resultado"]["xp"] == 21
    assert r["consola"][-1] == {"texto": "El área es 20.0"}

    intento.refresh_from_db()
    assert intento.estado == IntentoCodigo.RESUELTO
    assert (intento.estrellas, intento.xp_obtenida, intento.bloques_usados) == (2, 21, 4)
    # Ya resuelto no se vuelve a cobrar XP
    assert _comprobar(client, intento, _solucion(AREA)).status_code == 409
    # El menú muestra las estrellas y el siguiente acceso abre el nivel 2
    assert "⭐ 2 de 24 estrellas" in client.get("/jugar/").content.decode()
    assert client.get("/jugar/codigo/")["Location"] == f"/jugar/codigo/{MAYOR}/"
    assert _estado(client)["niveles"][0]["estrellas"] == 2


@pytest.mark.django_db
def test_recargar_retoma_el_ultimo_acomodo(client):
    intento = _abrir(client)
    mal = _p(("l1", 0), ("l3", 0), ("l2", 0), ("l4", 0))
    _comprobar(client, intento, mal)
    estado = _estado(client)
    assert estado["intento_id"] == str(intento.id) and estado["programa"] == mal
    assert estado["intentos_fallidos"] == 1 and IntentoCodigo.objects.count() == 1


@pytest.mark.django_db
def test_fa3_salir_regresa_al_menu_sin_xp(client):
    intento = _abrir(client)
    respuesta = client.post(f"/api/codigo/{intento.id}/salir/")
    assert respuesta.json()["codigo"]["url"] == "/jugar/"
    intento.refresh_from_db()
    assert intento.estado == IntentoCodigo.ABANDONADO and intento.xp_obtenida == 0
    assert _comprobar(client, intento, _solucion(AREA)).status_code == 409
    # Al volver a entrar empieza un intento nuevo
    assert _abrir(client).id != intento.id


@pytest.mark.django_db
def test_jugar_otra_vez_abre_un_intento_nuevo(client):
    intento = _abrir(client)
    _comprobar(client, intento, _solucion(AREA))
    assert _abrir(client).id == intento.id  # sin «otra vez» se ve el resultado
    nuevo = _abrir(client, MESA + "?nuevo=1")
    assert nuevo.id != intento.id and nuevo.estado == IntentoCodigo.EN_CURSO


@pytest.mark.django_db
def test_el_intento_es_solo_de_su_jugador(client, django_user_model):
    intento = _abrir(client)
    otro = django_user_model.objects.create_user("otro", password="x")
    client.force_login(otro)
    assert _comprobar(client, intento, _solucion(AREA)).status_code == 404
