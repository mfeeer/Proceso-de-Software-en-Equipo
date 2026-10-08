"""CU01 - Realizar Partida: motor del juego, API del libro y conexion con CU02."""

import json

import pytest

from app.models import Partida
from app.services import escenarios, motor_partida
from app.views_personalizar import PERFILES

PERFIL = PERFILES[0]  # Recién egresado: teoría 1, equipo 4, inteligencia 4
TRES = ["ingenieria-requerimientos:0", "ingenieria-requerimientos:1", "ingenieria-requerimientos:2"]


def _partida(temas=None, semilla=1, perfil=PERFIL):
    return motor_partida.crear_partida(perfil, temas or TRES, semilla=semilla)


def _tipos(partida):
    _, catalogo = escenarios.cargar()
    return [catalogo["eventos"][e]["tipo"] for e in partida.secuencia]


def _opcion(partida, correcta=True):
    """Id de una opcion correcta (o incorrecta) del evento actual; lee la partida al dia."""
    partida.refresh_from_db()
    _, catalogo = escenarios.cargar()
    evento = catalogo["eventos"][partida.secuencia[partida.indice]]
    for opcion in evento["opciones"]:
        if evento["tipo"] == escenarios.NORMAL and opcion["correcta"] == correcta:
            return opcion["id"]
    return evento["opciones"][0]["id"]


def _url(partida, accion=""):
    return f"/partida/{partida.id}/{accion}"


def _post(client, url, datos=None):
    return client.post(url, json.dumps(datos or {}), content_type="application/json")


def _jugar_hasta_el_final(client, partida):
    estado = client.get(_url(partida, "estado/")).json()
    while estado["fase"] != "fin":
        if estado["fase"] == "mejora":
            estado = _post(client, _url(partida, "mejorar/"), {"atributo": "teoria"}).json()
            continue
        _post(client, _url(partida, "decision/"), {"opcion_id": _opcion(partida)})
        estado = _post(client, _url(partida, "continuar/")).json()
    return estado


# ---------------------------------------------------------------- archivos de contenido
def test_los_archivos_de_escenarios_son_validos():
    assert escenarios.validar() == []


def test_escenarios_cubren_todos_los_subtemas_de_cu02_con_un_evento_de_cada_tipo():
    from app.views_personalizar import TEMAS

    _, catalogo = escenarios.cargar()
    for subtema in TEMAS:
        tipos = sorted(e["tipo"] for e in catalogo["eventos"].values() if e["subtema"] == subtema)
        assert tipos == [escenarios.NORMAL, escenarios.PROBABILIDAD], subtema


def test_desenlaces_cuentan_la_consecuencia():
    _, catalogo = escenarios.cargar()
    for evento in catalogo["eventos"].values():
        for opcion in evento["opciones"]:
            for campo in ("desenlace", "desenlace_exito", "desenlace_fallo"):
                if campo in opcion:
                    assert opcion[campo].count(". ") >= 1, (evento["id"], opcion["id"], campo)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "jugados, titulo, etiqueta",
    [
        (1, "El Primer Commit", "Final 1 de 4"),
        (5, "El Primer Commit", "Final 1 de 4"),
        (6, "Atorado a Medio Sprint", "Final 2 de 4"),
        (12, "Tan Cerca del Release", "Final 3 de 4"),
        (19, "A Un Paso de la Meta", "Final 4 de 4"),
        (40, "A Un Paso de la Meta", "Final 4 de 4"),
    ],
)
def test_final_de_derrota_depende_de_hasta_donde_llego(jugados, titulo, etiqueta):
    config, _ = escenarios.cargar()
    partida = _partida()
    partida.estado, partida.decisiones = Partida.DERROTA, jugados
    final, texto = motor_partida.final_de(partida, config)
    assert final["titulo"] == titulo and texto == etiqueta


# ---------------------------------------------------------------- creacion de la partida
@pytest.mark.django_db
def test_partida_toma_vidas_xp_y_atributos_del_perfil():
    partida = _partida()
    assert partida.hp == partida.hp_max == PERFIL["vidas"]
    assert partida.xp == PERFIL["xp"]
    assert partida.atributos == {"teoria": 1, "equipo": 4, "inteligencia": 4}


def test_perfiles_equilibrados_y_lobo_solitario():
    for perfil in PERFILES:
        assert perfil["teoria"] + perfil["equipo"] + perfil["inteligencia"] == 9, perfil["id"]
        assert perfil["vidas"] == 3 and perfil["xp"] == 0
    lobo = next(p for p in PERFILES if p["id"] == "lobo-solitario")
    assert lobo["equipo"] == 1 and lobo["teoria"] > 3 and lobo["inteligencia"] > 3


@pytest.mark.django_db
def test_dos_eventos_por_subtema_uno_normal_y_uno_de_probabilidad():
    partida = _partida()
    assert len(partida.secuencia) == 6
    assert _tipos(partida).count(escenarios.NORMAL) == 3


@pytest.mark.django_db
@pytest.mark.parametrize("temas", [TRES[:1], TRES[:2], TRES])
@pytest.mark.parametrize("semilla", range(25))
def test_el_bloque_1_solo_tiene_eventos_normales(temas, semilla):
    partida = _partida(temas=temas, semilla=semilla)
    config, _ = escenarios.cargar()
    total = len(partida.secuencia)
    for posicion, tipo in enumerate(_tipos(partida)):
        if motor_partida.bloque_de(posicion, total, config)[0] == 0:
            assert tipo == escenarios.NORMAL


@pytest.mark.django_db
def test_el_bloque_3_tiene_mas_probabilidad_que_el_bloque_2():
    bloque2 = bloque3 = 0
    for semilla in range(300):
        tipos = _tipos(_partida(semilla=semilla))
        bloque2 += tipos[2:4].count(escenarios.PROBABILIDAD)
        bloque3 += tipos[4:].count(escenarios.PROBABILIDAD)
    assert bloque3 > bloque2 > 0


@pytest.mark.django_db
def test_maximo_de_eventos_por_partida(monkeypatch):
    config, _ = escenarios.cargar()
    monkeypatch.setitem(config, "max_eventos_por_partida", 3)
    assert len(_partida().secuencia) == 3


@pytest.mark.django_db
def test_partida_requiere_tema_y_perfil():
    with pytest.raises(motor_partida.ReglaError):
        motor_partida.crear_partida(PERFIL, [])
    with pytest.raises(motor_partida.ReglaError):
        motor_partida.crear_partida(None, TRES)
    with pytest.raises(motor_partida.ReglaError):
        motor_partida.crear_partida(PERFIL, ["no-existe:0"])


def test_probabilidad_depende_del_atributo_y_se_limita():
    config, _ = escenarios.cargar()
    opcion = {"atributo": "teoria", "probabilidad_base": 30}
    assert motor_partida.probabilidad_opcion(opcion, {"teoria": 0}, config) == 30
    assert motor_partida.probabilidad_opcion(opcion, {"teoria": 3}, config) == 48
    assert motor_partida.probabilidad_opcion(opcion, {"teoria": 50}, config) == 95
    assert motor_partida.probabilidad_opcion({**opcion, "probabilidad_base": 0}, {}, config) == 5


# ---------------------------------------------------------------- conexion con CU02
@pytest.mark.django_db
def test_comenzar_aventura_crea_la_partida_y_abre_el_libro(client):
    client.post("/personalizar/", {"perfil": "carrera-afin"})
    respuesta = client.post("/personalizar/modulo/", {"tema": TRES[:2]}, follow=True)
    partida = Partida.objects.get()
    assert respuesta.redirect_chain[-1][0] == f"/partida/{partida.id}/"
    assert partida.perfil_nombre == "Carrera afín, sin software"
    assert partida.temas == TRES[:2] and partida.xp == 0 and len(partida.secuencia) == 4
    assert "pt-estado" in respuesta.content.decode()
    # Refrescar /personalizar/comenzar/ no crea otra partida
    client.get("/personalizar/comenzar/")
    assert Partida.objects.count() == 1


@pytest.mark.django_db
def test_se_pueden_mezclar_materias_y_elegir_mas_de_3_temas(client):
    temas = ["intro-programacion:0", "logica-algoritmos:1", "programacion-oo:0", *TRES]
    client.post("/personalizar/", {"perfil": "abierto"})
    respuesta = client.post("/personalizar/modulo/", {"tema": temas})
    assert respuesta.status_code == 302
    client.get(respuesta["Location"])
    partida = Partida.objects.get()
    assert partida.temas == temas
    assert len(partida.secuencia) == 12  # 6 subtemas x 2 eventos (tope: 20)
    _, catalogo = escenarios.cargar()
    assert len({catalogo["eventos"][e]["tema_id"] for e in partida.secuencia}) == 4


@pytest.mark.django_db
def test_perfiles_de_cu02_muestran_los_atributos_del_juego(client):
    html = client.get("/personalizar/").content.decode()
    assert "📚 Teoría 1" in html and "🤝 Equipo 4" in html and "💡 Inteligencia 4" in html
    assert "Lobo solitario" in html and 'data-max="10"' in html
    assert "teoría baja" not in html


# ---------------------------------------------------------------- jugar (API)
@pytest.mark.django_db
def test_el_estado_no_revela_respuestas(client):
    cuerpo = client.get(_url(_partida(), "estado/")).content.decode()
    assert "correcta" not in cuerpo and "desenlace" not in cuerpo
    assert json.loads(cuerpo)["fase"] == "evento"


@pytest.mark.django_db
def test_acertar_sube_xp_puntos_y_progreso(client):
    partida = _partida()
    estado = _post(client, _url(partida, "decision/"), {"opcion_id": _opcion(partida)}).json()
    assert estado["fase"] == "resultado" and estado["resultado"]["acierto"] is True
    assert estado["resultado"]["retroalimentacion"] and estado["resultado"]["desenlace"]
    assert estado["xp"] == 10 and estado["puntuacion"] == 100 and estado["hp"] == 3
    assert estado["progreso"] == round(100 / 6)
    assert partida.registros.count() == 1


@pytest.mark.django_db
def test_fallar_resta_vida_y_no_da_xp(client):
    partida = _partida()
    estado = _post(
        client, _url(partida, "decision/"), {"opcion_id": _opcion(partida, correcta=False)}
    ).json()
    assert estado["resultado"]["acierto"] is False
    assert estado["hp"] == 2 and estado["xp"] == 0


@pytest.mark.django_db
def test_no_se_avanza_sin_ver_la_retroalimentacion(client):
    partida = _partida()
    opcion = _opcion(partida)
    _post(client, _url(partida, "decision/"), {"opcion_id": opcion})
    assert client.get(_url(partida, "estado/")).json()["fase"] == "resultado"
    assert _post(client, _url(partida, "decision/"), {"opcion_id": opcion}).status_code == 409
    estado = _post(client, _url(partida, "continuar/")).json()
    assert estado["fase"] == "evento" and estado["evento_numero"] == 2
    assert _post(client, _url(partida, "continuar/")).status_code == 409


@pytest.mark.django_db
def test_opcion_inexistente_se_rechaza(client):
    assert _post(client, _url(_partida(), "decision/"), {"opcion_id": "z"}).status_code == 409


@pytest.mark.django_db
def test_cada_5_aciertos_se_sube_de_nivel_y_se_gana_un_punto(client):
    partida = _partida()
    estado = client.get(_url(partida, "estado/")).json()
    assert estado["nivel"] == 1 and estado["xp_por_nivel"] == 50
    partida.xp = 40  # ya lleva 4 aciertos
    partida.save()
    _post(client, _url(partida, "decision/"), {"opcion_id": _opcion(partida)})
    estado = _post(client, _url(partida, "continuar/")).json()
    assert estado["fase"] == "mejora" and estado["nivel"] == 2 and estado["puntos_atributo"] == 1
    assert _post(client, _url(partida, "decision/"), {"opcion_id": "a"}).status_code == 409
    estado = _post(client, _url(partida, "mejorar/"), {"atributo": "teoria"}).json()
    assert estado["fase"] == "evento" and estado["puntos_atributo"] == 0
    assert {a["id"]: a["valor"] for a in estado["atributos"]}["teoria"] == 2
    assert _post(client, _url(partida, "mejorar/"), {"atributo": "teoria"}).status_code == 409


@pytest.mark.django_db
def test_nivel_y_atributos_tienen_maximo_10():
    config, _ = escenarios.cargar()
    assert motor_partida.nivel_de(10_000, config) == 10
    assert motor_partida.valor_atributo(99, config) == 10
    partida = _partida()
    partida.atributos["teoria"] = 10
    partida.puntos_atributo = 1
    partida.save()
    with pytest.raises(motor_partida.ReglaError):
        motor_partida.mejorar_atributo(partida, "teoria")
    motor_partida.mejorar_atributo(partida, "equipo")
    assert partida.atributos["equipo"] == 5


@pytest.mark.django_db
def test_evento_de_probabilidad_muestra_porcentaje_y_tira_en_el_servidor(client):
    partida = _partida()
    partida.indice = _tipos(partida).index(escenarios.PROBABILIDAD)
    partida.save()
    opcion = client.get(_url(partida, "estado/")).json()["evento"]["opciones"][0]
    assert 5 <= opcion["probabilidad"] <= 95 and opcion["atributo_nombre"]
    estado = _post(client, _url(partida, "decision/"), {"opcion_id": opcion["id"]}).json()
    riesgo = estado["resultado"]["riesgo"]
    assert riesgo["probabilidad"] == opcion["probabilidad"] and riesgo["mensaje"]
    assert estado["resultado"]["acierto"] == (riesgo["tirada"] <= riesgo["probabilidad"])


@pytest.mark.django_db
def test_sin_vidas_la_partida_termina_en_derrota(client):
    partida = _partida()
    partida.hp = 1
    partida.save()
    estado = _post(
        client, _url(partida, "decision/"), {"opcion_id": _opcion(partida, correcta=False)}
    ).json()
    assert estado["resultado"]["estado_final"] == Partida.DERROTA
    # Primero se ve el desenlace desfavorable; luego, Post Game con opción de volver a empezar.
    assert client.get(_url(partida, "fin/")).status_code == 302
    assert _post(client, _url(partida, "continuar/")).json()["fase"] == "fin"
    html = client.get(_url(partida, "fin/")).content.decode()
    assert "El Primer Commit" in html and "Final 1 de 4" in html
    assert "Comenzar nueva partida" in html


@pytest.mark.django_db
def test_partida_completa_muestra_puntuacion_logros_y_mapa(client):
    partida = _partida()
    _jugar_hasta_el_final(client, partida)
    partida.refresh_from_db()
    assert partida.estado == Partida.COMPLETADA and "capitulo_cerrado" in partida.logros
    html = client.get(_url(partida, "fin/")).content.decode()
    assert "Mapa de decisiones" in html and "Capítulo cerrado" in html
    assert html.count('class="pt-paso ') == 6
    assert client.get(_url(partida)).status_code == 302  # el libro ya cerrado manda al final


@pytest.mark.django_db
def test_paginas_responden(client):
    partida = _partida()
    html = client.get(_url(partida)).content.decode()
    assert "css/partida.css" in html and "js/partida.js" in html and 'id="ajustes-btn"' in html
    assert client.get("/partida/00000000-0000-0000-0000-000000000000/").status_code == 404
