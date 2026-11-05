"""CU04 - Resolver minijuego de código: se abre desde el menú de modos (CU05).

SDS 1.3.4 y 3.3.2; reglas CU04-RN01 a RN05. Hay 4 niveles por tema, cada uno con varios
programas en Python y pseudocódigo y cada programa con varias variantes de valores; al jugar se
elige uno al azar y sus líneas salen revueltas. Cubre el contenido, la revisión del acomodo
(varias soluciones válidas, sangría, orden, distractores), la calificación y la API de la mesa.
"""

import json
import re

import pytest
from django.core.management import call_command

from app.models import IntentoCodigo
from app.services import minijuego_codigo

MESA = "/jugar/codigo/python/1/"


def _nivel(programa, lenguaje="python", variante=0):
    return minijuego_codigo.armar(programa, lenguaje, variante)


def _p(*lineas):
    """_p(("l1", 0), ("l2", 1)) -> [{"id": "l1", "sangria": 0}, ...]"""
    return [{"id": lid, "sangria": sangria} for lid, sangria in lineas]


def _solucion(nivel_):
    return [{"id": ln["id"], "sangria": ln["sangria"]} for ln in nivel_["lineas"]]


def _revisar(nivel_, programa):
    return minijuego_codigo.revisar_programa(programa, nivel_)


def _notas(revision):
    return {e["linea_id"]: e["nota"] for e in revision["errores"]}


def _abrir(client, url=MESA):
    assert client.get(url).status_code == 200
    return IntentoCodigo.objects.latest("creado")


def _fijar(intento, programa, lenguaje="python", variante=0):
    """El programa y la variante salen al azar: las pruebas fijan uno conocido."""
    intento.nivel_id = f"{programa}-{lenguaje}"
    intento.variante = variante
    intento.save()
    return intento


def _comprobar(client, intento, programa):
    url = f"/api/codigo/{intento.id}/comprobar/"
    return client.post(url, json.dumps({"programa": programa}), content_type="application/json")


def _estado(client, url=MESA):
    html = client.get(url).content.decode()
    inicio = html.index('id="mj-estado"')
    return json.loads(html[html.index(">", inicio) + 1 : html.index("</script>", inicio)])


AREA = _p(("l1", 0), ("l2", 0), ("l3", 0), ("l4", 0))
AREA_MAL = _p(("l1", 0), ("l3", 0), ("l2", 0), ("l4", 0))  # el área antes de leer la altura


# ---------------------------------------------------------------- contenido (RNF-MAN-05, 07)
def test_hay_4_niveles_con_3_programas_y_3_variantes_cada_uno():
    assert minijuego_codigo.validar() == []
    catalogo = minijuego_codigo.cargar()
    assert [n["nombre"] for n in catalogo["niveles"]] == [
        "Secuencia",
        "Decisiones",
        "Ciclos",
        "Ciclos con decisiones",
    ]
    for numero, sobran in ((1, 0), (2, 0), (3, 1), (4, 2)):
        programas = minijuego_codigo.programas_del_nivel(numero)
        assert len(programas) == 3
        for programa in programas:
            assert len(catalogo["programas"][programa]["variantes"]) == 3
            for lenguaje in minijuego_codigo.LENGUAJES:
                # Los distractores aparecen desde el nivel 3
                assert len(_nivel(programa, lenguaje)["distractores"]) == sobran


def test_validar_escenarios_revisa_el_minijuego(capsys):
    call_command("validar_escenarios")
    salida = capsys.readouterr().out
    assert (
        "Minijuego de código válido: 4 niveles con 12 programas y 36 variantes, en 2 lenguajes."
        in salida
    )


def _programa_de_prueba(lineas, variantes=None):
    return {
        "id": "prueba",
        "nivel": 1,
        "titulo": "Prueba",
        "objetivo": "Probar",
        "variantes": variantes or [{}],
        "lenguajes": {
            leng: {"lineas": lineas, "consola": [{"texto": "1"}]}
            for leng in minijuego_codigo.LENGUAJES
        },
    }


def test_el_validador_detecta_reglas_que_no_cumple_su_propia_solucion():
    lineas = [
        {"id": "l1", "codigo": "x = 1", "sangria": 0, "despues_de": ["l2"]},
        {"id": "l2", "codigo": "print(x)", "sangria": 0},
    ]
    errores = []
    assert not minijuego_codigo._validar_programa(
        _programa_de_prueba(lineas), "p.json", {1}, errores
    )
    assert "no cumplen sus reglas" in errores[0]

    repetidas = [
        {"id": "l1", "codigo": "print(x)", "sangria": 0},
        {"id": "l2", "codigo": "print(x)", "sangria": 0},
    ]
    errores = []
    minijuego_codigo._validar_programa(_programa_de_prueba(repetidas), "p.json", {1}, errores)
    assert any("se repite" in e for e in errores)


def test_el_validador_pide_todos_los_valores_de_cada_variante():
    lineas = [
        {"id": "l1", "codigo": "{a} = 1", "sangria": 0},
        {"id": "l2", "codigo": "print({a})", "sangria": 0, "despues_de": ["l1"]},
    ]
    errores = []
    datos = _programa_de_prueba(lineas, [{"a": "x"}, {"b": "y"}])
    assert not minijuego_codigo._validar_programa(datos, "p.json", {1}, errores)
    assert errores == ["niveles_codigo/p.json > variante 2: faltan los valores a"]


# ---------------------------------------------------------------- variantes y varias soluciones
def test_la_solucion_de_cada_programa_y_variante_es_correcta():
    catalogo = minijuego_codigo.cargar()
    for programa, datos in catalogo["programas"].items():
        for lenguaje in minijuego_codigo.LENGUAJES:
            for variante in range(len(datos["variantes"])):
                nivel_ = _nivel(programa, lenguaje, variante)
                assert _revisar(nivel_, _solucion(nivel_))["correcta"], (programa, lenguaje)
                # Ya no queda ningún {marcador} sin valor
                textos = [ln["codigo"] for ln in nivel_["lineas"] + nivel_["distractores"]]
                textos += [nivel_["objetivo"], *(c["texto"] for c in nivel_["consola"])]
                assert not any(minijuego_codigo.MARCADOR.search(t) for t in textos)


def test_cada_variante_cambia_nombres_valores_y_ejemplo():
    a, b = _nivel("mayor-de-dos", "python", 0), _nivel("mayor-de-dos", "python", 1)
    assert a["lineas"][2]["codigo"] == "if a > b:" and b["lineas"][2]["codigo"] == "if x > y:"
    assert a["consola"][-1] == {"texto": "El mayor es 8"}
    assert b["consola"][-1] == {"texto": "El mayor es 9"}
    minimos = [_nivel("aprobado", "pseudocodigo", i)["lineas"][3]["codigo"] for i in range(3)]
    assert minimos == [f"Si calificacion >= {n} Entonces" for n in (6, 7, 8)]


def test_los_datos_se_pueden_leer_en_cualquier_orden():
    area = _nivel("area-rectangulo")
    assert _revisar(area, _p(("l2", 0), ("l1", 0), ("l3", 0), ("l4", 0)))["correcta"]
    mayor = _nivel("mayor-de-dos", "pseudocodigo")
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
    assert _revisar(mayor, otro_orden)["correcta"]
    # El nombre se puede leer en cualquier momento antes de escribir el resultado
    edad = _nivel("edad-en-dias")
    assert _revisar(edad, _p(("l2", 0), ("l3", 0), ("l1", 0), ("l4", 0)))["correcta"]


# ---------------------------------------------------------------- FE1 y FE3: no se califica
def test_fe3_programa_vacio():
    r = _revisar(_nivel("area-rectangulo"), [])
    assert r["vacio"] and not r["completo"] and r["titulo"] == "El programa está vacío"


def test_fe1_faltan_lineas():
    r = _revisar(_nivel("area-rectangulo"), _p(("l1", 0), ("l2", 0)))
    assert not r["completo"] and r["faltan"] == 2
    assert r["mensaje"] == "Todavía quedan 2 líneas del programa en el banco."


# ---------------------------------------------------------------- FE2: reglas que no se cumplen
def test_fe2_una_operacion_antes_de_sus_datos():
    r = _revisar(_nivel("area-rectangulo"), AREA_MAL)
    assert r["completo"] and not r["correcta"]
    assert _notas(r) == {"l3": "está demasiado arriba"}
    assert r["mensaje"] == (
        '«area = base * altura» debe ir después de «altura = float(input("Altura: "))».'
    )


def test_fe2_sangria_que_falta_y_sangria_de_mas():
    mayor = _nivel("mayor-de-dos")
    r = _revisar(mayor, _p(("l1", 0), ("l2", 0), ("l3", 0), ("l4", 0), ("l5", 0), ("l6", 1)))
    assert _notas(r)["l4"] == "dale sangría"
    assert r["mensaje"] == '«print("El mayor es", a)» debe ir dentro de «if a > b:»: dale sangría.'

    dentro_de_otra = _p(("l1", 0), ("l2", 1), ("l3", 0), ("l4", 1), ("l5", 0), ("l6", 1))
    assert _notas(_revisar(mayor, dentro_de_otra)) == {"l2": "quítale sangría"}
    de_mas = _p(("l1", 0), ("l2", 2), ("l3", 0), ("l4", 1), ("l5", 0), ("l6", 1))
    assert _notas(_revisar(mayor, de_mas)) == {"l2": "sangría de más"}


def test_fe2_else_debe_ir_despues_del_bloque_del_if():
    mayor = _nivel("mayor-de-dos")
    # else entre el if y lo que tiene adentro: lo de adentro queda en el else
    r = _revisar(mayor, _p(("l1", 0), ("l2", 0), ("l3", 0), ("l5", 0), ("l4", 1), ("l6", 1)))
    assert not r["correcta"] and "l4" in _notas(r)
    # else antes del if
    r = _revisar(mayor, _p(("l1", 0), ("l2", 0), ("l5", 0), ("l6", 1), ("l3", 0), ("l4", 1)))
    assert _notas(r)["l5"] == "va justo después de otro bloque"


def test_fe2_fin_si_antes_de_tiempo_en_pseudocodigo():
    programa = _p(
        ("l1", 0),
        ("l2", 1),
        ("l3", 1),
        ("l4", 1),
        ("l5", 2),
        ("l8", 1),  # FinSi antes del SiNo
        ("l6", 1),
        ("l7", 2),
        ("l9", 0),
    )
    r = _revisar(_nivel("mayor-de-dos", "pseudocodigo"), programa)
    assert not r["correcta"] and {"l8", "l6"} & set(_notas(r))


def test_fe2_un_distractor_no_va_en_el_programa():
    suma = _nivel("suma-hasta-n")
    con_distractor = _p(("l1", 0), ("l2", 0), ("l3", 0), ("l4", 1), ("d1", 1), ("l5", 0))
    r = _revisar(suma, con_distractor)
    assert _notas(r) == {"d1": "esta línea sobra"}
    assert (
        r["mensaje"] == "«for i in range(1, n):» no forma parte de la solución: regrésala al banco."
    )
    # Usar el distractor en lugar de la línea buena deja el programa incompleto
    cambiado = _p(("l1", 0), ("l2", 0), ("d1", 0), ("l4", 1), ("l5", 0))
    assert not _revisar(suma, cambiado)["completo"]


# ---------------------------------------------------------------- calificar (RN01, RN03 a RN05)
@pytest.mark.parametrize(
    "fallos, estrellas, xp",
    [
        (0, 3, 40),  # a la primera: 100% de la XP del nivel 2
        (1, 2, 28),  # 75% de 40 = 30, menos 5% por el fallo (RN05)
        (2, 2, 27),  # 30 menos 10%
        (3, 1, 17),  # 50% de 40 = 20, menos 15%
        (30, 1, 10),  # la penalización se detiene en −50%
    ],
)
def test_estrellas_y_xp(fallos, estrellas, xp):
    reglas = minijuego_codigo.cargar()["reglas"]
    r = minijuego_codigo.calificar(fallos, _nivel("mayor-de-dos"), reglas)
    assert (r["estrellas"], r["xp"]) == (estrellas, xp)


# ---------------------------------------------------------------- menú de modos y rondas
def _resolver(client, url):
    """Abre el nivel y lo resuelve a la primera con la solución del programa que tocó."""
    intento = _abrir(client, url)
    solucion = _solucion(minijuego_codigo.nivel_de(intento))
    return intento, _comprobar(client, intento, solucion).json()["codigo"]


@pytest.mark.django_db
def test_el_menu_de_modos_abre_el_minijuego(client):
    html = client.get("/jugar/").content.decode()
    assert 'href="/jugar/codigo/"' in html and "Pseudocódigo" in html
    respuesta = client.get("/jugar/codigo/")
    assert respuesta.status_code == 302 and respuesta["Location"] == MESA
    respuesta = client.get("/jugar/codigo/?lenguaje=pseudocodigo")
    assert respuesta["Location"] == "/jugar/codigo/pseudocodigo/1/"


@pytest.mark.django_db
def test_se_recuerda_el_ultimo_lenguaje(client):
    _abrir(client, "/jugar/codigo/pseudocodigo/1/")
    assert client.get("/jugar/codigo/")["Location"] == "/jugar/codigo/pseudocodigo/1/"


@pytest.mark.django_db
def test_los_niveles_no_se_pueden_saltar(client):
    assert client.get("/jugar/codigo/java/1/").status_code == 404
    assert client.get("/jugar/codigo/python/9/").status_code == 404
    respuesta = client.get("/jugar/codigo/python/3/")
    assert respuesta.status_code == 302 and respuesta["Location"] == MESA
    _resolver(client, MESA)
    assert client.get("/jugar/codigo/python/3/")["Location"] == "/jugar/codigo/python/2/"


@pytest.mark.django_db
def test_cada_intento_es_un_programa_y_variante_del_nivel(client):
    intento = _abrir(client)
    programas = minijuego_codigo.programas_del_nivel(1)
    assert intento.nivel_id in {f"{p}-python" for p in programas}
    assert 0 <= intento.variante < 3 and intento.ronda == 1


@pytest.mark.django_db
def test_una_ronda_completa_y_la_siguiente_con_otros_programas(client):
    primera = []
    for numero in (1, 2, 3, 4):
        # «Jugar minijuego» siempre lleva al nivel que sigue
        url = f"/jugar/codigo/python/{numero}/"
        assert client.get("/jugar/codigo/")["Location"] == url
        intento, r = _resolver(client, url)
        primera.append(intento.nivel_id)
        assert r["correcta"] and r["ronda"]["completa"] == (numero == 4)
        assert r["ronda"]["siguiente"] == (numero + 1 if numero < 4 else None)
        # Un nivel ya resuelto de la ronda muestra su resultado
        assert _abrir(client, url).id == intento.id

    ronda = r["ronda"]
    assert [n["estado"] for n in ronda["niveles"]] == ["hecho"] * 4
    assert (ronda["estrellas"], ronda["estrellas_max"], ronda["xp"]) == (12, 12, 180)
    assert (ronda["en_juego"], ronda["de"], ronda["ultima"], ronda["juego"]) == (1, 3, False, None)

    # Al volver a jugar empieza la ronda 2 en el nivel 1, con otro programa
    assert client.get("/jugar/codigo/")["Location"] == MESA
    nuevo = _abrir(client)
    assert nuevo.ronda == 2 and nuevo.estado == IntentoCodigo.EN_CURSO
    assert nuevo.nivel_id != primera[0]
    estado = _estado(client)
    assert (estado["ronda"]["numero"], estado["ronda"]["en_juego"]) == (2, 2)
    assert [n["estado"] for n in estado["ronda"]["niveles"]] == ["actual"] + ["pendiente"] * 3


def _jugar_ronda(client):
    """Resuelve los 4 niveles de la ronda en curso. Devuelve {nivel: (programa, variante)}."""
    tocaron = {}
    for _ in range(4):
        url = client.get("/jugar/codigo/")["Location"]
        intento, r = _resolver(client, url)
        tocaron[int(url.rstrip("/").split("/")[-1])] = (intento.nivel_id, intento.variante)
    return tocaron, r["ronda"]


@pytest.mark.django_db
def test_un_juego_son_3_rondas_sin_repetir_programas(client):
    rondas = []
    for numero in (1, 2, 3):
        tocaron, ronda = _jugar_ronda(client)
        rondas.append(tocaron)
        assert ronda["en_juego"] == numero and ronda["completa"]
        assert ronda["ultima"] == (numero == 3)

    # En cada nivel, las 3 rondas usaron sus 3 programas, sin repetir ninguno
    for nivel in (1, 2, 3, 4):
        programas = {rondas[i][nivel][0] for i in range(3)}
        assert programas == {f"{p}-python" for p in minijuego_codigo.programas_del_nivel(nivel)}

    # Al terminar la ronda 3 se acaba el juego, con el resumen de sus 3 rondas
    juego = ronda["juego"]
    assert [r["numero"] for r in juego["rondas"]] == [1, 2, 3]
    assert (juego["estrellas"], juego["estrellas_max"], juego["xp"]) == (36, 36, 540)

    # Volver a jugar empieza otro juego: sus programas vuelven a salir, pero con otra variante
    variantes_antes = {p: v for tocaron in rondas for p, v in tocaron.values()}
    tocaron, ronda = _jugar_ronda(client)
    assert ronda["numero"] == 4 and ronda["en_juego"] == 1 and not ronda["ultima"]
    for programa, variante in tocaron.values():
        assert variante != variantes_antes[programa]


@pytest.mark.django_db
def test_la_mesa_de_trabajo_carga_el_nivel_sin_sus_reglas(client):
    intento = _fijar(_abrir(client), "area-rectangulo", variante=1)
    html = client.get(MESA).content.decode()
    assert "Área de un rectángulo" in html and 'id="mj-ayuda"' in html
    assert "RONDA 1 DE 3 · NIVEL 1" in html
    assert "css/taller.css" in html and "js/minijuego_codigo.js" in html
    # La versión de los archivos va en la URL para que el navegador no use una copia vieja
    assert re.search(r"js/minijuego_codigo\.js\?v=[1-9]\d*\"", html)
    assert re.search(r"css/minijuego_codigo\.css\?v=[1-9]\d*\"", html)

    estado = _estado(client)
    assert estado["intento_id"] == str(intento.id)
    lineas = estado["nivel"]["lineas"]
    assert all(set(ln) == {"id", "codigo"} for ln in lineas)  # sin sangría, padre ni orden
    assert [ln["id"] for ln in lineas] != ["l1", "l2", "l3", "l4"]  # nunca en orden
    assert 'largo = float(input("Largo: "))' in [ln["codigo"] for ln in lineas]  # variante 2
    assert _estado(client)["nivel"]["lineas"] == lineas  # el mismo revuelto al recargar
    niveles = estado["ronda"]["niveles"]
    assert [n["nombre"] for n in niveles][0] == "Secuencia"
    assert [n["estado"] for n in niveles] == ["actual", "pendiente", "pendiente", "pendiente"]
    assert estado["urls"]["niveles"]["2"] == "/jugar/codigo/python/2/"
    assert estado["urls"]["otra_ronda"] == "/jugar/codigo/?lenguaje=python"
    otro = {leng["id"]: leng["url"] for leng in estado["lenguajes"]}
    assert otro["pseudocodigo"] == "/jugar/codigo/?lenguaje=pseudocodigo"


@pytest.mark.django_db
def test_programa_mal_formado_se_rechaza(client):
    intento = _fijar(_abrir(client), "area-rectangulo")
    assert _comprobar(client, intento, _p(("x9", 0))).status_code == 400
    assert _comprobar(client, intento, _p(("l1", 0), ("l1", 0))).status_code == 400
    assert _comprobar(client, intento, _p(("l1", 9))).status_code == 400
    url = f"/api/codigo/{intento.id}/comprobar/"
    assert client.post(url, "{}", content_type="application/json").status_code == 400


# ---------------------------------------------------------------- flujo completo por la API
@pytest.mark.django_db
def test_incompleto_no_cuenta_como_intento_fallido(client):
    intento = _fijar(_abrir(client), "area-rectangulo")
    r = _comprobar(client, intento, _p(("l1", 0))).json()["codigo"]
    assert not r["completo"] and r["intentos_fallidos"] == 0


@pytest.mark.django_db
def test_rn02_el_mismo_acomodo_no_se_cobra_dos_veces(client):
    intento = _fijar(_abrir(client), "area-rectangulo")
    r = _comprobar(client, intento, AREA_MAL).json()["codigo"]
    assert not r["correcta"] and r["intentos_fallidos"] == 1 and not r["repetido"]
    r = _comprobar(client, intento, AREA_MAL).json()["codigo"]
    assert r["repetido"] and r["intentos_fallidos"] == 1
    otro_mal = _p(("l4", 0), ("l1", 0), ("l2", 0), ("l3", 0))
    assert _comprobar(client, intento, otro_mal).json()["codigo"]["intentos_fallidos"] == 2


@pytest.mark.django_db
def test_flujo_normal_resolver_y_pasar_al_siguiente_nivel(client):
    intento = _fijar(_abrir(client), "area-rectangulo")
    _comprobar(client, intento, AREA_MAL)  # 1 fallo
    r = _comprobar(client, intento, _p(("l2", 0), ("l1", 0), ("l3", 0), ("l4", 0))).json()
    r = r["codigo"]
    assert r["correcta"] and r["resultado"]["estrellas"] == 2 and r["resultado"]["xp"] == 21
    assert r["consola"][-1] == {"texto": "El área es 20.0"}
    assert r["ronda"]["siguiente"] == 2 and not r["ronda"]["completa"]
    assert r["ronda"]["niveles"][0] == {
        "numero": 1,
        "nombre": "Secuencia",
        "estado": "hecho",
        "estrellas": 2,
    }

    intento.refresh_from_db()
    assert intento.estado == IntentoCodigo.RESUELTO
    assert (intento.estrellas, intento.xp_obtenida, intento.bloques_usados) == (2, 21, 4)
    # Ya resuelto no se vuelve a cobrar XP
    assert _comprobar(client, intento, AREA).status_code == 409
    # El menú muestra las estrellas y el siguiente acceso abre el nivel 2
    assert "⭐ 2 de 24 estrellas" in client.get("/jugar/").content.decode()
    assert client.get("/jugar/codigo/")["Location"] == "/jugar/codigo/python/2/"


@pytest.mark.django_db
def test_recargar_retoma_el_mismo_programa_y_acomodo(client):
    intento = _fijar(_abrir(client), "area-rectangulo", variante=2)
    _comprobar(client, intento, AREA_MAL)
    estado = _estado(client)
    assert estado["intento_id"] == str(intento.id) and estado["programa"] == AREA_MAL
    assert estado["intentos_fallidos"] == 1 and IntentoCodigo.objects.count() == 1
    assert 'lado1 = float(input("Lado 1: "))' in [ln["codigo"] for ln in estado["nivel"]["lineas"]]


@pytest.mark.django_db
def test_fa3_salir_regresa_al_menu_sin_xp(client):
    intento = _fijar(_abrir(client), "area-rectangulo")
    respuesta = client.post(f"/api/codigo/{intento.id}/salir/")
    assert respuesta.json()["codigo"]["url"] == "/jugar/"
    intento.refresh_from_db()
    assert intento.estado == IntentoCodigo.ABANDONADO and intento.xp_obtenida == 0
    assert _comprobar(client, intento, AREA).status_code == 409
    # Al volver sigue en el mismo nivel de la ronda, con otro programa
    assert client.get("/jugar/codigo/")["Location"] == MESA
    nuevo = _abrir(client)
    assert nuevo.id != intento.id and nuevo.ronda == 1
    assert nuevo.nivel_id != "area-rectangulo-python"


@pytest.mark.django_db
def test_el_intento_es_solo_de_su_jugador(client, django_user_model):
    intento = _fijar(_abrir(client), "area-rectangulo")
    otro = django_user_model.objects.create_user("otro", password="x")
    client.force_login(otro)
    assert _comprobar(client, intento, AREA).status_code == 404
