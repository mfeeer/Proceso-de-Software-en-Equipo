"""CU05 - Completar cuestionario de tecnicismos, y los cambios a CU01 que lo hacen posible.

SDS 1.3.5 y 3.3.3; SRS RF-39 a RF-41 (CU01) y RF-51 a RF-60 (CU05).
"""

import json
import random
import time

import pytest
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.management import call_command

from app.models import ResultadoCuestionario, TecnicismoRegistrado
from app.services import cuestionario, escenarios, motor_partida, tecnicismos
from app.services.tecnicismos import Jugador
from app.views_personalizar import PERFILES

PERFIL = PERFILES[0]
TRES = ["ingenieria-requerimientos:0", "ingenieria-requerimientos:1", "ingenieria-requerimientos:2"]
GENERAR = "/api/cuestionario/generar/"
RESULTADO = "/api/cuestionario/resultado/"
REGLAS = {
    "minimo_tecnicismos": 4,
    "preguntas_por_cuestionario": 10,
    "opciones_por_pregunta": 4,
    "dias_validez_cuestionario": 30,
}


def _catalogo():
    return tecnicismos.cargar()[1]


def _post(client, url, datos=None):
    return client.post(url, json.dumps(datos or {}), content_type="application/json")


def _jugador(client):
    """Jugador anonimo de la sesion del cliente de pruebas (la crea si no existe)."""
    client.get("/jugar/")
    return Jugador(sesion=client.session.session_key)


def _dar(client, cantidad=None, ids=None):
    """Registra tecnicismos al jugador del cliente, como si los hubiera visto en CU01."""
    jugador = _jugador(client)
    ids = ids if ids is not None else list(_catalogo())[:cantidad]
    tecnicismos.registrar(jugador, ids)
    return jugador, ids


def _evento(partida):
    partida.refresh_from_db()
    _, catalogo = escenarios.cargar()
    return catalogo["eventos"][partida.secuencia[partida.indice]]


def _respuestas_correctas(datos, aciertos=None):
    """Respuestas del cuestionario acertando las primeras `aciertos` preguntas (todas si None)."""
    total = len(datos["preguntas"])
    aciertos = total if aciertos is None else aciertos
    return [
        p["correcta"] if i < aciertos else (p["correcta"] + 1) % len(p["opciones"])
        for i, p in enumerate(datos["preguntas"])
    ]


def _tec(tid, nombre, escenario="", clave="dato", descripcion=None):
    return {
        "id": tid,
        "nombre": nombre,
        "subtema": "x:0",
        "descripcion": descripcion or f"Descripción con un {clave} de {nombre}.",
        "escenario_aplicacion": escenario,
        "palabra_clave": clave,
        "formas": [nombre],
    }


# ================================================================ catálogo (RNF-MAN-07)
def test_el_catalogo_de_tecnicismos_y_los_escenarios_son_validos():
    assert escenarios.validar() == []


def test_cada_tecnicismo_del_catalogo_se_puede_descubrir_en_algun_evento():
    _, catalogo = escenarios.cargar()
    declarados = {t for e in catalogo["eventos"].values() for t in e.get("tecnicismos", [])}
    assert set(catalogo["tecnicismos"]) == declarados


def test_cada_tecnicismo_tiene_los_datos_de_la_precondicion():
    for tec in _catalogo().values():
        for campo in ("nombre", "descripcion", "escenario_aplicacion", "palabra_clave"):
            assert tec[campo].strip(), (tec["id"], campo)
        assert tecnicismos.patron(tec["palabra_clave"]).search(tec["descripcion"]), tec["id"]


def test_el_catalogo_detecta_errores_de_contenido():
    errores = []
    datos = {
        "reglas": REGLAS,
        "tecnicismos": [
            _tec("a", "Uno", clave="ausente", descripcion="No trae la palabra."),
            _tec("b", "Uno"),
        ],
    }
    tecnicismos.leer(datos, "prueba.json", errores)
    assert any("palabra_clave 'ausente'" in e for e in errores)
    assert any("nombre 'uno' se repite" in e for e in errores)


def test_un_evento_no_puede_declarar_tecnicismos_inexistentes_o_que_no_aparecen():
    catalogo = {"a": _tec("a", "Trazabilidad")}
    eventos = [
        {"id": "e1", "contexto": "Sin el término.", "opciones": [], "tecnicismos": ["a"]},
        {"id": "e2", "contexto": "Algo", "opciones": [], "tecnicismos": ["zzz"]},
    ]
    errores = tecnicismos.validar_eventos(eventos, catalogo, "prueba")
    assert any("e1" in e and "no aparece" in e for e in errores)
    assert any("e2" in e and "no existe" in e for e in errores)


def test_el_comando_validar_escenarios_incluye_los_tecnicismos(capsys):
    call_command("validar_escenarios")
    assert "Escenarios válidos" in capsys.readouterr().out


def test_las_formas_se_buscan_como_palabra_completa_sin_importar_mayusculas():
    assert tecnicismos.patron("except").search("usa un EXCEPT vacío")
    assert not tecnicismos.patron("except").search("captura excepciones")
    assert not tecnicismos.patron("int").search("interpretar")


# ================================================================ cambios a CU01 (RF-39 a RF-41)
@pytest.mark.django_db
def test_rf39_rf40_el_estado_del_evento_trae_sus_tecnicismos_con_su_explicacion():
    partida = motor_partida.crear_partida(PERFIL, TRES, semilla=1)
    estado = motor_partida.estado_publico(partida)
    evento = _evento(partida)
    ids = [t["id"] for t in estado["tecnicismos"]]
    assert ids == evento["tecnicismos"] and ids
    for tec in estado["tecnicismos"]:
        assert set(tec) == {"id", "nombre", "descripcion", "formas"}
        assert tecnicismos.aparece(tec, tecnicismos.texto_visible(evento))


@pytest.mark.django_db
def test_rf41_al_mostrar_un_evento_se_registran_sus_tecnicismos(client):
    partida = motor_partida.crear_partida(PERFIL, TRES, semilla=1)
    respuesta = client.get(f"/partida/{partida.id}/estado/")
    datos = respuesta.json()
    jugador = Jugador(sesion=client.session.session_key)
    esperados = _evento(partida)["tecnicismos"]
    assert datos["tecnicismos_nuevos"] == esperados
    assert sorted(tecnicismos.registrados(jugador)) == sorted(esperados)
    registro = TecnicismoRegistrado.objects.get(sesion=jugador.sesion, tecnicismo_id=esperados[0])
    assert registro.partida_id == partida.id


@pytest.mark.django_db
def test_rn02_el_registro_no_se_duplica_al_volver_a_ver_el_evento(client):
    partida = motor_partida.crear_partida(PERFIL, TRES, semilla=1)
    client.get(f"/partida/{partida.id}/")  # la página del libro también registra
    segunda = client.get(f"/partida/{partida.id}/estado/").json()
    assert segunda["tecnicismos_nuevos"] == []
    total = TecnicismoRegistrado.objects.filter(sesion=client.session.session_key).count()
    assert total == len(_evento(partida)["tecnicismos"])


@pytest.mark.django_db
def test_rn02_el_registro_es_acumulativo_y_se_conserva_entre_partidas(client):
    primera = motor_partida.crear_partida(PERFIL, TRES, semilla=1)
    client.get(f"/partida/{primera.id}/estado/")
    antes = set(tecnicismos.registrados(_jugador(client)))
    otra = motor_partida.crear_partida(PERFIL, ["programacion-oo:0"], semilla=2)
    client.get(f"/partida/{otra.id}/estado/")
    despues = set(tecnicismos.registrados(_jugador(client)))
    assert antes < despues
    assert set(_evento(otra)["tecnicismos"]) <= despues


@pytest.mark.django_db
def test_al_decidir_se_registra_el_siguiente_evento_y_el_resultado_trae_tecnicismos(client):
    partida = motor_partida.crear_partida(PERFIL, TRES, semilla=1)
    client.get(f"/partida/{partida.id}/estado/")
    evento = _evento(partida)
    opcion = next(o["id"] for o in evento["opciones"] if o.get("correcta", True))
    resultado = _post(client, f"/partida/{partida.id}/decision/", {"opcion_id": opcion}).json()
    assert resultado["fase"] == "resultado"
    assert [t["id"] for t in resultado["tecnicismos"]] == evento["tecnicismos"]
    assert resultado["tecnicismos_nuevos"] == []  # el resultado no registra nada
    siguiente = _post(client, f"/partida/{partida.id}/continuar/").json()
    if siguiente["fase"] == "evento":
        nuevos = set(_evento(partida)["tecnicismos"]) - set(evento["tecnicismos"])
        assert set(siguiente["tecnicismos_nuevos"]) == nuevos


@pytest.mark.django_db
def test_el_registro_es_por_usuario_cuando_hay_sesion_iniciada(client):
    usuario = get_user_model().objects.create_user("ana", password="clave-segura-123")
    client.force_login(usuario)
    partida = motor_partida.crear_partida(PERFIL, TRES, usuario=usuario, semilla=1)
    client.get(f"/partida/{partida.id}/estado/")
    assert TecnicismoRegistrado.objects.filter(usuario=usuario).exists()
    assert not TecnicismoRegistrado.objects.filter(usuario__isnull=True).exists()
    otro = Jugador(sesion="otra-sesion")
    assert tecnicismos.registrados(otro) == []


# ================================================================ menú de modos (RF-51)
@pytest.mark.django_db
def test_iniciar_juego_lleva_al_menu_de_tres_modos(client):
    assert 'href="/jugar/"' in client.get("/").content.decode()
    html = client.get("/jugar/").content.decode()
    assert "Historia narrativa" in html and "Cuestionario súbito" in html
    assert "Minijuego de código" in html  # CU04, aún en desarrollo
    assert 'href="/personalizar/"' in html  # FA2: Historia narrativa ejecuta CU01 (vía CU02)


@pytest.mark.django_db
def test_fa1_el_menu_muestra_el_cuestionario_bloqueado_con_el_avance(client):
    _dar(client, 2)
    html = client.get("/jugar/").content.decode()
    assert "🔒 Bloqueado" in html
    assert "Has descubierto 2 de 4 tecnicismos necesarios" in html
    assert 'href="/jugar/cuestionario/"' not in html


@pytest.mark.django_db
def test_con_cuatro_tecnicismos_el_menu_desbloquea_el_cuestionario(client):
    _dar(client, 4)
    html = client.get("/jugar/").content.decode()
    assert "¡DESBLOQUEADO!" in html and 'href="/jugar/cuestionario/"' in html


@pytest.mark.django_db
def test_la_pagina_del_cuestionario_carga(client):
    respuesta = client.get("/jugar/cuestionario/")
    assert respuesta.status_code == 200
    assert "js/cuestionario.js" in respuesta.content.decode()


# ================================================================ generación (pasos 4 a 6)
@pytest.mark.django_db
def test_fa1_rn03_con_menos_de_cuatro_tecnicismos_no_se_genera(client):
    _dar(client, 3)
    respuesta = _post(client, GENERAR)
    assert respuesta.status_code == 409
    datos = respuesta.json()
    assert datos["error"] == "insuficientes"
    assert (datos["registrados"], datos["necesarios"]) == (3, 4)
    assert "Has descubierto 3 de 4" in datos["mensaje"]


@pytest.mark.django_db
def test_rn05_con_cuatro_registrados_hay_cuatro_preguntas_sin_repetir(client):
    _, ids = _dar(client, 4)
    datos = _post(client, GENERAR).json()
    preguntados = [p["tecnicismo_id"] for p in datos["preguntas"]]
    assert datos["total"] == 4 and len(set(preguntados)) == 4
    assert set(preguntados) == set(ids)  # RN01


@pytest.mark.django_db
def test_rn05_con_mas_de_diez_registrados_hay_diez_preguntas_sin_repetir(client):
    _dar(client, 15)
    datos = _post(client, GENERAR).json()
    preguntados = [p["tecnicismo_id"] for p in datos["preguntas"]]
    assert len(preguntados) == 10 and len(set(preguntados)) == 10


@pytest.mark.django_db
def test_rn01_rn04_cuatro_opciones_una_correcta_y_distractores_de_registrados(client):
    _, ids = _dar(client, 6)
    catalogo = _catalogo()
    registrados = [catalogo[i] for i in ids]
    for _ in range(10):
        for p in _post(client, GENERAR).json()["preguntas"]:
            assert len(p["opciones"]) == 4 and len(set(p["opciones"])) == 4
            dato = cuestionario.DATO_DEL_TIPO[p["tipo"]]
            validos = {t[dato] for t in registrados}
            assert set(p["opciones"]) <= validos  # solo datos de tecnicismos registrados
            correctas = [o for o in p["opciones"] if o == catalogo[p["tecnicismo_id"]][dato]]
            assert correctas == [p["opciones"][p["correcta"]]]


@pytest.mark.django_db
def test_rn01_un_registro_que_ya_no_esta_en_el_catalogo_no_se_pregunta(client):
    jugador, _ = _dar(client, 4)
    TecnicismoRegistrado.objects.create(**jugador.campos(), tecnicismo_id="ya-no-existe")
    datos = _post(client, GENERAR).json()
    assert "ya-no-existe" not in {p["tecnicismo_id"] for p in datos["preguntas"]}


def test_tipos_de_pregunta_a_b_y_c():
    catalogo = _catalogo()
    tec = catalogo["trazabilidad"]
    otros = [t for t in catalogo.values() if t["id"] != "trazabilidad"][:6]
    vistos = {}
    for semilla in range(60):
        p = cuestionario.armar_pregunta(1, tec, otros, random.Random(semilla))
        vistos[p["tipo"]] = p
    a, b, c = vistos["A"], vistos["B"], vistos["C"]
    assert a["texto"] == tec["descripcion"] and not a["nombre"]
    assert a["opciones"][a["correcta"]] == tec["nombre"]
    assert b["nombre"] == tec["nombre"] and b["texto"] == tec["descripcion"]
    assert b["opciones"][b["correcta"]] == tec["escenario_aplicacion"]
    assert cuestionario.HUECO in c["texto"] and tec["palabra_clave"] not in c["texto"]
    assert c["opciones"][c["correcta"]] == tec["palabra_clave"]


def test_fa5_si_falta_el_dato_del_tipo_asignado_se_usa_otro():
    sin_escenario = _tec("x", "Sin escenario", escenario="")
    otros = [_tec(f"o{i}", f"Otro {i}", f"Escenario {i}", f"clave{i}") for i in range(4)]
    asignados_b = 0
    for semilla in range(80):
        p = cuestionario.armar_pregunta(1, sin_escenario, otros, random.Random(semilla))
        assert p["tipo"] in {"A", "C"}
        asignados_b += p["tipo_asignado"] == "B"
    assert asignados_b > 0  # sí hubo preguntas a las que les tocó B y se cambiaron


def test_fa5_sin_distractores_suficientes_para_un_tipo_se_usa_otro():
    tec = _tec("x", "Uno", "Escenario único", "clave")
    otros = [_tec(f"o{i}", f"Otro {i}", "", f"k{i}") for i in range(3)]  # sin escenarios
    assert not cuestionario.disponible(tec, "B", otros, 4)
    assert cuestionario.disponible(tec, "A", otros, 4)


@pytest.mark.django_db
def test_el_orden_de_las_opciones_es_aleatorio(client):
    _dar(client, 10)
    posiciones = set()
    for _ in range(8):
        posiciones |= {p["correcta"] for p in _post(client, GENERAR).json()["preguntas"]}
    assert posiciones == {0, 1, 2, 3}


@pytest.mark.django_db
def test_el_cuestionario_se_genera_en_menos_de_dos_segundos(client):
    _dar(client, len(_catalogo()))
    inicio = time.perf_counter()
    respuesta = _post(client, GENERAR)
    assert respuesta.status_code == 200
    assert time.perf_counter() - inicio < 2


@pytest.mark.django_db
def test_fa4_cada_partida_del_cuestionario_es_nueva(client):
    _dar(client, 8)
    uno, dos = _post(client, GENERAR).json(), _post(client, GENERAR).json()
    assert uno["cuestionario_id"] != dos["cuestionario_id"]


@pytest.mark.django_db
def test_fa3_generar_o_abandonar_no_guarda_resultado_ni_cambia_el_registro(client):
    jugador, ids = _dar(client, 5)
    _post(client, GENERAR)  # el usuario sale sin terminar: el navegador descarta todo
    assert ResultadoCuestionario.objects.count() == 0
    assert sorted(tecnicismos.registrados(jugador)) == sorted(ids)


# ================================================================ resultado (pasos 10 y 11)
@pytest.mark.parametrize(
    ("aciertos", "total", "esperado"),
    [(7, 10, 70), (10, 10, 100), (0, 4, 0), (1, 3, 33), (2, 3, 67), (1, 8, 13), (3, 8, 38)],
)
def test_rn06_puntaje_es_aciertos_entre_total_por_cien(aciertos, total, esperado):
    assert cuestionario.puntaje(aciertos, total) == esperado


@pytest.mark.django_db
def test_rf58_se_guarda_fecha_puntaje_y_respuestas_por_tecnicismo(client):
    _dar(client, 10)
    datos = _post(client, GENERAR).json()
    fecha = "2026-10-21T18:42:00-06:00"
    respuesta = _post(
        client,
        RESULTADO,
        {"token": datos["token"], "respuestas": _respuestas_correctas(datos, 7), "fecha": fecha},
    )
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert (cuerpo["puntaje"], cuerpo["aciertos"], cuerpo["total"]) == (70, 7, 10)
    assert cuerpo["origen"] == ResultadoCuestionario.EN_LINEA
    guardado = ResultadoCuestionario.objects.get(pk=datos["cuestionario_id"])
    assert guardado.sesion == client.session.session_key
    assert len(guardado.respuestas) == 10
    primera = guardado.respuestas[0]
    assert primera["tecnicismo_id"] == datos["preguntas"][0]["tecnicismo_id"]
    assert primera["acierto"] is True and primera["elegida"] == primera["correcta"]
    assert guardado.respuestas[9]["acierto"] is False


@pytest.mark.django_db
def test_el_servidor_recalcula_el_puntaje_con_el_token_firmado(client):
    _dar(client, 4)
    datos = _post(client, GENERAR).json()
    # El navegador podría alterar "correcta" en su copia; el servidor usa la del token.
    respuestas = [(p["correcta"] + 1) % 4 for p in datos["preguntas"]]
    cuerpo = _post(client, RESULTADO, {"token": datos["token"], "respuestas": respuestas}).json()
    assert cuerpo["puntaje"] == 0


@pytest.mark.django_db
def test_fe1_reintentar_un_resultado_no_lo_duplica(client):
    _dar(client, 4)
    datos = _post(client, GENERAR).json()
    cuerpo = {
        "token": datos["token"],
        "respuestas": _respuestas_correctas(datos),
        "pendiente": True,
    }
    primera = _post(client, RESULTADO, cuerpo)
    segunda = _post(client, RESULTADO, cuerpo)
    assert (primera.status_code, segunda.status_code) == (201, 200)
    assert segunda.json()["cuestionario_id"] == primera.json()["cuestionario_id"]
    assert ResultadoCuestionario.objects.count() == 1


@pytest.mark.django_db
def test_fe1_un_resultado_pendiente_se_guarda_como_sincronizado_con_su_fecha(client):
    _dar(client, 4)
    datos = _post(client, GENERAR).json()
    respuesta = _post(
        client,
        RESULTADO,
        {
            "token": datos["token"],
            "respuestas": _respuestas_correctas(datos),
            "fecha": datos["generado"],
            "pendiente": True,
        },
    )
    assert respuesta.json()["origen"] == ResultadoCuestionario.SINCRONIZADO
    guardado = ResultadoCuestionario.objects.get()
    assert guardado.fecha.isoformat()[:19] == datos["generado"][:19]


@pytest.mark.django_db
def test_un_token_alterado_se_rechaza(client):
    _dar(client, 4)
    datos = _post(client, GENERAR).json()
    token = datos["token"][:-3] + ("aaa" if not datos["token"].endswith("aaa") else "bbb")
    respuesta = _post(client, RESULTADO, {"token": token, "respuestas": [0, 0, 0, 0]})
    assert respuesta.status_code == 400
    assert ResultadoCuestionario.objects.count() == 0


@pytest.mark.django_db
def test_no_se_puede_guardar_el_cuestionario_de_otro_jugador(client):
    ajeno = signing.dumps(
        {"id": "5f1c2b9e-8d4a-4c1e-9a77-3b0f2d6e1a10", "j": "s:otro", "g": "2026-10-21", "p": []},
        salt=cuestionario.SAL_FIRMA,
        compress=True,
    )
    _jugador(client)
    respuesta = _post(client, RESULTADO, {"token": ajeno, "respuestas": []})
    assert respuesta.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("respuestas", [[0, 1], [0, 1, 2, 9], [0, 1, 2, True], "0123", None])
def test_respuestas_incompletas_o_invalidas_se_rechazan(client, respuestas):
    _dar(client, 4)
    datos = _post(client, GENERAR).json()
    respuesta = _post(client, RESULTADO, {"token": datos["token"], "respuestas": respuestas})
    assert respuesta.status_code == 400
    assert ResultadoCuestionario.objects.count() == 0


@pytest.mark.django_db
def test_el_menu_muestra_el_ultimo_puntaje(client):
    _dar(client, 4)
    datos = _post(client, GENERAR).json()
    _post(client, RESULTADO, {"token": datos["token"], "respuestas": _respuestas_correctas(datos)})
    assert "Último puntaje: 100" in client.get("/jugar/").content.decode()
