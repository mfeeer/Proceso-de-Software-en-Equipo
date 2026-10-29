"""CU06 - Conseguir vidas: afirmaciones, reglas del minijuego y API (SDS 1.3.6 y 3.3.1)."""

import json
import random

import pytest

from app.models import Partida
from app.services import conseguir_vidas, escenarios, motor_partida
from app.views_personalizar import PERFILES

PERFIL = PERFILES[0]
TRES = ["ingenieria-requerimientos:0", "ingenieria-requerimientos:1", "ingenieria-requerimientos:2"]


def _partida(hp=2, temas=None):
    partida = motor_partida.crear_partida(PERFIL, temas or TRES, semilla=1)
    partida.hp = hp
    partida.save()
    return partida


def _url(partida, accion=""):
    return f"/partida/{partida.id}/{accion}"


def _post(client, url, datos=None):
    return client.post(url, json.dumps(datos or {}), content_type="application/json")


def _vidas(estado):
    return estado["vidas"]


def _correcta(partida, acertar=True):
    """Respuesta correcta (o incorrecta) para la afirmacion en juego."""
    partida.refresh_from_db()
    ronda = partida.vidas_extra["ronda"]
    pid = ronda["preguntas"][len(ronda["respuestas"])]
    respuesta = conseguir_vidas.cargar_preguntas()[pid]["respuesta"]
    return respuesta if acertar else not respuesta


def _jugar_ronda(client, partida, aciertos):
    """Juega una ronda completa por la API acertando las primeras `aciertos` afirmaciones."""
    _post(client, _url(partida, "vidas/iniciar/"))
    estado = None
    for numero in range(5):
        respuesta = _correcta(partida, acertar=numero < aciertos)
        estado = _post(client, _url(partida, "vidas/responder/"), {"respuesta": respuesta}).json()
    return estado


def _opcion(partida, correcta=True):
    partida.refresh_from_db()
    _, catalogo = escenarios.cargar()
    evento = catalogo["eventos"][partida.secuencia[partida.indice]]
    for opcion in evento["opciones"]:
        if evento["tipo"] == escenarios.NORMAL and opcion["correcta"] == correcta:
            return opcion["id"]
    return evento["opciones"][0]["id"]


def _decidir_y_pasar(client, partida, correcta=True):
    _post(client, _url(partida, "decision/"), {"opcion_id": _opcion(partida, correcta)})
    estado = _post(client, _url(partida, "continuar/")).json()
    if estado["fase"] == "mejora":
        estado = _post(client, _url(partida, "mejorar/"), {"atributo": "teoria"}).json()
    return estado


# ---------------------------------------------------------------- contenido y reglas
def test_afirmaciones_y_reglas_validas():
    assert conseguir_vidas.validar() == []
    config, _ = escenarios.cargar()
    reglas = conseguir_vidas.reglas(config)
    assert (reglas["preguntas_por_ronda"], reglas["aciertos_minimos"]) == (5, 4)
    assert (reglas["vidas_por_ronda"], reglas["eventos_para_sugerencia"]) == (1, 5)


def test_cinco_afirmaciones_por_subtema_con_verdaderas_y_falsas():
    _, catalogo = escenarios.cargar()
    preguntas = conseguir_vidas.cargar_preguntas()
    assert len(preguntas) == 50
    for tema in catalogo["temas"].values():
        for subtema in tema["subtemas"]:
            del_subtema = [p for p in preguntas.values() if p["subtema"] == subtema["id"]]
            assert len(del_subtema) == 5, subtema["id"]
            assert {p["respuesta"] for p in del_subtema} == {True, False}, subtema["id"]


def test_el_validador_detecta_errores(tmp_path, monkeypatch):
    archivo = tmp_path / "preguntas_vidas.json"
    archivo.write_text(
        json.dumps(
            {"preguntas": [{"id": "x", "subtema": "no-existe:0", "afirmacion": "", "respuesta": 1}]}
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(conseguir_vidas, "PREGUNTAS_PATH", archivo)
    errores = " | ".join(conseguir_vidas.validar())
    assert "no-existe:0" in errores and "'afirmacion'" in errores and "'respuesta'" in errores


@pytest.mark.django_db
def test_la_ronda_prefiere_los_temas_de_la_partida_y_no_repite_las_vistas():
    partida = _partida(temas=["programacion-oo:1"])
    preguntas = conseguir_vidas.cargar_preguntas()
    rng = random.Random(4)
    primera = conseguir_vidas._elegir_preguntas(partida, preguntas, [], 5, rng)
    assert len(set(primera)) == 5
    assert all(preguntas[p]["subtema"] == "programacion-oo:1" for p in primera)
    segunda = conseguir_vidas._elegir_preguntas(partida, preguntas, primera, 5, rng)
    assert not set(primera) & set(segunda)
    assert all(preguntas[p]["subtema"] == "programacion-oo:0" for p in segunda)  # misma materia


# ---------------------------------------------------------------- CU06-RN02 disponibilidad
@pytest.mark.django_db
@pytest.mark.parametrize("hp, disponible", [(0, False), (1, True), (2, True), (3, False)])
def test_solo_disponible_con_1_o_2_vidas(client, hp, disponible):
    partida = _partida(hp=hp)
    assert conseguir_vidas.puede_conseguir(partida) is disponible
    assert _vidas(client.get(_url(partida, "estado/")).json())["disponible"] is disponible


@pytest.mark.django_db
def test_con_vidas_completas_no_se_puede_iniciar(client):
    respuesta = _post(client, _url(_partida(hp=3), "vidas/iniciar/"))
    assert respuesta.status_code == 409
    assert respuesta.json() == {"error": "Ya tienes todas tus vidas."}


# ---------------------------------------------------------------- flujo normal y CU06-RN01
@pytest.mark.django_db
def test_la_pregunta_en_juego_nunca_incluye_su_respuesta(client):
    partida = _partida()
    estado = _post(client, _url(partida, "vidas/iniciar/")).json()
    ronda = _vidas(estado)["ronda"]
    assert ronda["numero"] == 1 and ronda["total"] == 5 and ronda["ultima"] is None
    assert set(ronda["pregunta"]) == {"id", "afirmacion", "tema"}
    assert _vidas(estado)["eventos"] == 0 and _vidas(estado)["sugerir"] is False


@pytest.mark.django_db
def test_responder_devuelve_la_respuesta_correcta_y_la_explicacion(client):
    partida = _partida()
    _post(client, _url(partida, "vidas/iniciar/"))
    url = _url(partida, "vidas/responder/")
    ronda = _vidas(_post(client, url, {"respuesta": _correcta(partida)}).json())["ronda"]
    assert ronda["ultima"]["correcta"] is True and ronda["ultima"]["explicacion"]
    assert ronda["numero"] == 2 and ronda["respondidas"] == 1 and ronda["resultados"] == [True]
    ronda = _vidas(_post(client, url, {"respuesta": _correcta(partida, False)}).json())["ronda"]
    ultima = ronda["ultima"]
    assert ultima["correcta"] is False and ultima["respuesta"] != ultima["respuesta_usuario"]
    assert ronda["resultados"] == [True, False] and ronda["aciertos"] == 1
    assert ronda["terminada"] is False and ronda["exito"] is None


@pytest.mark.django_db
def test_4_de_5_aciertos_suman_una_vida(client):
    partida = _partida(hp=1)
    estado = _jugar_ronda(client, partida, aciertos=4)
    ronda = _vidas(estado)["ronda"]
    assert ronda["terminada"] is True and ronda["exito"] is True and ronda["vidas_ganadas"] == 1
    assert estado["hp"] == 2 and _vidas(estado)["recuperadas"] == 1
    assert _vidas(estado)["disponible"] is True  # aun le falta una


@pytest.mark.django_db
def test_paso_11_salir_cierra_el_resultado(client):
    partida = _partida(hp=1)
    _jugar_ronda(client, partida, aciertos=5)
    # Recargar antes de cerrar vuelve a mostrar el resultado
    assert _vidas(client.get(_url(partida, "estado/")).json())["ronda"]["terminada"] is True
    estado = _post(client, _url(partida, "vidas/salir/")).json()
    assert _vidas(estado)["ronda"] is None and estado["hp"] == 2


@pytest.mark.django_db
def test_fa3_al_llegar_a_3_vidas_se_deshabilita_y_se_detiene_el_conteo(client):
    partida = _partida(hp=2)
    partida.vidas_extra = {"eventos": 3}
    partida.save()
    estado = _jugar_ronda(client, partida, aciertos=5)
    assert estado["hp"] == 3 and _vidas(estado)["disponible"] is False
    assert _vidas(estado)["eventos"] == 0 and _vidas(estado)["sugerir"] is False
    _post(client, _url(partida, "vidas/salir/"))
    assert _post(client, _url(partida, "vidas/iniciar/")).status_code == 409


@pytest.mark.django_db
def test_fe1_con_3_aciertos_no_se_gana_la_vida(client):
    partida = _partida(hp=2)
    estado = _jugar_ronda(client, partida, aciertos=3)
    ronda = _vidas(estado)["ronda"]
    assert ronda["exito"] is False and ronda["vidas_ganadas"] == 0
    assert estado["hp"] == 2 and _vidas(estado)["disponible"] is True


@pytest.mark.django_db
def test_nunca_se_pasa_del_maximo(client, monkeypatch):
    config, _ = escenarios.cargar()
    monkeypatch.setitem(config["conseguir_vidas"], "vidas_por_ronda", 5)
    assert _jugar_ronda(client, _partida(hp=2), aciertos=5)["hp"] == 3


@pytest.mark.django_db
def test_fa2_acepta_verdadero_falso_y_rechaza_otra_cosa(client):
    partida = _partida()
    _post(client, _url(partida, "vidas/iniciar/"))
    url = _url(partida, "vidas/responder/")
    texto = "verdadero" if _correcta(partida) else "falso"
    assert _vidas(_post(client, url, {"respuesta": texto}).json())["ronda"]["aciertos"] == 1
    assert _post(client, url, {"respuesta": "tal vez"}).status_code == 409
    assert _post(client, url).status_code == 409


@pytest.mark.django_db
def test_recargar_retoma_la_misma_pregunta_sin_volver_a_sortear(client):
    partida = _partida()
    _post(client, _url(partida, "vidas/iniciar/"))
    _post(client, _url(partida, "vidas/responder/"), {"respuesta": _correcta(partida)})
    antes = _vidas(client.get(_url(partida, "estado/")).json())["ronda"]
    despues = _vidas(_post(client, _url(partida, "vidas/iniciar/")).json())["ronda"]
    assert despues["numero"] == 2 and despues["pregunta"] == antes["pregunta"]
    partida.refresh_from_db()
    assert partida.vidas_extra["rondas"] == 1


@pytest.mark.django_db
def test_no_se_puede_decidir_en_la_historia_con_una_ronda_en_juego(client):
    partida = _partida()
    _post(client, _url(partida, "vidas/iniciar/"))
    respuesta = _post(client, _url(partida, "decision/"), {"opcion_id": _opcion(partida)})
    assert respuesta.status_code == 409 and "minijuego" in respuesta.json()["error"]


@pytest.mark.django_db
def test_las_rondas_no_repiten_afirmaciones_vistas(client):
    partida = _partida(hp=1)
    _post(client, _url(partida, "vidas/iniciar/"))
    _post(client, _url(partida, "vidas/salir/"))
    _post(client, _url(partida, "vidas/iniciar/"))
    partida.refresh_from_db()
    extra = partida.vidas_extra
    assert len(extra["vistas"]) == 10 and len(set(extra["vistas"])) == 10
    assert extra["rondas"] == 2


# ---------------------------------------------------------------- FE2 abandonar
@pytest.mark.django_db
def test_fe2_salir_a_media_ronda_no_da_la_vida(client):
    partida = _partida(hp=2)
    _post(client, _url(partida, "vidas/iniciar/"))
    for _ in range(4):
        _post(client, _url(partida, "vidas/responder/"), {"respuesta": _correcta(partida)})
    estado = _post(client, _url(partida, "vidas/salir/")).json()
    assert estado["hp"] == 2 and _vidas(estado)["ronda"] is None
    respuesta = _post(client, _url(partida, "vidas/responder/"), {"respuesta": True})
    assert respuesta.status_code == 409


# ---------------------------------------------------------------- FA1 sugerencia
@pytest.mark.django_db
def test_fa1_sugiere_el_minijuego_a_los_cinco_eventos(client):
    partida = _partida(hp=3)
    partida.secuencia = partida.secuencia * 3  # alcanza para 18 eventos
    partida.save()
    estado = _decidir_y_pasar(client, partida, correcta=False)  # pierde una vida: no cuenta
    assert estado["hp"] == 2 and _vidas(estado)["eventos"] == 0
    for numero in range(1, 5):
        estado = _decidir_y_pasar(client, partida)
        assert _vidas(estado)["eventos"] == numero and _vidas(estado)["sugerir"] is False
    estado = _decidir_y_pasar(client, partida)
    assert estado["fase"] == "evento" and _vidas(estado)["sugerir"] is True
    # "Ahora no": el conteo reinicia y el boton sigue disponible
    estado = _post(client, _url(partida, "vidas/sugerencia/")).json()
    assert _vidas(estado)["sugerir"] is False and _vidas(estado)["eventos"] == 0
    assert _vidas(estado)["disponible"] is True


@pytest.mark.django_db
def test_fa1_entrar_al_minijuego_reinicia_el_conteo(client):
    partida = _partida(hp=2)
    partida.vidas_extra = {"eventos": 5, "sugerir": True}
    partida.save()
    estado = _post(client, _url(partida, "vidas/iniciar/")).json()
    assert _vidas(estado)["eventos"] == 0 and _vidas(estado)["sugerir"] is False


@pytest.mark.django_db
def test_fa1_con_vidas_completas_no_se_cuenta(client):
    partida = _partida(hp=3)
    estado = _decidir_y_pasar(client, partida)
    assert _vidas(estado)["eventos"] == 0 and _vidas(estado)["sugerir"] is False


# ---------------------------------------------------------------- FE4 sin vidas
@pytest.mark.django_db
def test_fe4_al_perder_la_ultima_vida_no_hay_minijuego_ni_sugerencia(client):
    partida = _partida(hp=1)
    partida.vidas_extra = {"eventos": 4}
    partida.save()
    _post(client, _url(partida, "decision/"), {"opcion_id": _opcion(partida, correcta=False)})
    estado = client.get(_url(partida, "estado/")).json()
    assert estado["hp"] == 0 and estado["estado"] == Partida.DERROTA
    assert _vidas(estado)["disponible"] is False
    assert _vidas(estado)["sugerir"] is False and _vidas(estado)["eventos"] == 0
    respuesta = _post(client, _url(partida, "vidas/iniciar/"))
    assert respuesta.status_code == 409 and "terminó" in respuesta.json()["error"]


# ---------------------------------------------------------------- integracion con CU01
@pytest.mark.django_db
def test_las_vidas_recuperadas_cuentan_como_dano_para_sin_rasgunos():
    config, _ = escenarios.cargar()
    partida = _partida(hp=3)
    partida.estado = Partida.COMPLETADA
    assert "sin_rasgunos" in motor_partida._logros_ganados(partida, config)
    partida.vidas_extra = {"recuperadas": 1}
    assert "sin_rasgunos" not in motor_partida._logros_ganados(partida, config)


@pytest.mark.django_db
def test_partidas_sin_vidas_extra_funcionan(client):
    partida = _partida(hp=2)
    partida.vidas_extra = {}
    partida.save()
    vidas = _vidas(client.get(_url(partida, "estado/")).json())
    assert vidas["ronda"] is None and vidas["recuperadas"] == 0 and vidas["disponible"] is True


@pytest.mark.django_db
def test_el_libro_carga_el_minijuego_y_la_api_solo_acepta_post(client):
    partida = _partida()
    html = client.get(_url(partida)).content.decode()
    assert "css/vidas.css" in html and "js/vidas.js" in html
    assert client.get(_url(partida, "vidas/iniciar/")).status_code == 405
    falsa = "/partida/00000000-0000-0000-0000-000000000000/vidas/iniciar/"
    assert _post(client, falsa).status_code == 404
