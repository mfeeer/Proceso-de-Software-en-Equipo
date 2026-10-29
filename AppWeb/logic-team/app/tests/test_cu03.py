"""CU03 - Personalizar interfaz: engranaje de ajustes, panel de opciones y reglas del caso de uso.

Estas pruebas revisan lo que entrega el servidor (Django): que el engranaje y el panel aparezcan en
todas las pantallas, que ofrezcan las opciones del caso de uso, que los recursos existan y que los
ajustes no toquen la partida (RN04). El comportamiento en el navegador (aplicar, guardar, restaurar
y el aviso de FE1) se prueba con frontend/tests/ajustes.test.mjs, que corre el ajustes.js real.
"""

import re

import pytest
from django.contrib.staticfiles import finders

from app.models import Partida
from app.services import motor_partida
from app.views_personalizar import PERFILES

TEMAS = ["ingenieria-requerimientos:0", "ingenieria-requerimientos:1"]


def _partida():
    return motor_partida.crear_partida(PERFILES[0], TEMAS, semilla=1)


def _leer_estatico(ruta):
    with open(finders.find(ruta), encoding="utf-8") as archivo:
        return archivo.read()


def _pantallas(client):
    """HTML de cada pantalla del sistema: portada, CU02 (perfil y módulo), libro y Post Game."""
    partida = _partida()
    terminada = _partida()
    terminada.estado = Partida.DERROTA
    terminada.save()

    pantallas = {"Portada": client.get("/"), "Personalizar perfil": client.get("/personalizar/")}
    client.post("/personalizar/", {"perfil": "carrera-afin"})
    pantallas["Personalizar módulo"] = client.get("/personalizar/modulo/")
    pantallas["Libro de la partida"] = client.get(f"/partida/{partida.id}/")
    pantallas["Post Game"] = client.get(f"/partida/{terminada.id}/fin/")
    return pantallas


# ---------------------------------------------------------------- flujo normal
def test_flujo_normal_engranaje_y_recursos_en_la_portada(client):
    """Paso 1: en la portada está el engranaje y se cargan los estilos y el script de ajustes."""
    html = client.get("/").content.decode()
    assert 'id="ajustes-btn"' in html
    assert 'id="ajustes-panel"' in html
    assert "css/ajustes.css" in html
    assert "js/ajustes.js" in html
    # Opciones principales del panel
    for esperado in (
        'name="tamano"',
        'name="fuente"',
        'value="dislexia"',
        'id="aj-musica"',
        "Restaurar valores por defecto",
    ):
        assert esperado in html


@pytest.mark.django_db
def test_flujo_normal_engranaje_en_todas_las_pantallas(client):
    """Precondición y paso 1: el usuario tiene acceso al engranaje en cualquier pantalla."""
    for nombre, respuesta in _pantallas(client).items():
        assert respuesta.status_code == 200, nombre
        html = respuesta.content.decode()
        assert html.count('id="ajustes-btn"') == 1, nombre
        assert 'id="ajustes-panel"' in html, nombre
        assert "js/ajustes.js" in html and "css/ajustes.css" in html, nombre


def test_flujo_normal_panel_inicia_cerrado_y_lo_controla_el_engranaje(client):
    """Paso 1: el panel empieza oculto y el botón del engranaje es quien lo despliega."""
    html = client.get("/").content.decode()
    boton = re.search(r'<button[^>]*id="ajustes-btn"[^>]*>', html).group(0)
    panel = re.search(r'<section[^>]*id="ajustes-panel"[^>]*>', html).group(0)
    assert 'aria-controls="ajustes-panel"' in boton
    assert 'aria-expanded="false"' in boton
    assert " hidden" in panel and 'role="dialog"' in panel
    assert 'id="ajustes-cerrar"' in html


def test_flujo_normal_panel_muestra_todas_las_opciones(client):
    """Paso 2: el sistema despliega las opciones de tamaño, tipo de letra, vista y sonido."""
    html = client.get("/").content.decode()
    tamanos = re.findall(r'name="tamano" value="([^"]+)"', html)
    fuentes = re.findall(r'name="fuente" value="([^"]+)"', html)
    assert tamanos == ["pequeno", "normal", "grande", "muy-grande"]
    assert fuentes == ["libro", "dislexia", "legible"]
    for control in ('id="aj-contraste"', 'id="aj-movimiento"', 'id="aj-musica"'):
        assert control in html
    assert re.search(r'id="aj-volumen" min="0" max="100"', html)


@pytest.mark.django_db
def test_flujo_normal_preferencias_guardadas_se_aplican_al_cargar(client):
    """Paso 4 y postcondición: cada pantalla lee lo guardado antes de pintarse."""
    for nombre, respuesta in _pantallas(client).items():
        html = respuesta.content.decode()
        lectura = html.find('localStorage.getItem("logicteam.ajustes")')
        assert 0 <= lectura < html.find("</head>"), nombre
        for clave in ("tamano", "fuente", "contraste", "movimiento"):
            assert f'"{clave}"' in html[lectura : html.find("</head>")], nombre


def test_flujo_normal_estilos_para_cada_opcion():
    """Paso 4: cada valor del panel tiene un estilo que lo aplica a toda la aplicación."""
    css = _leer_estatico("css/ajustes.css")
    for selector in (
        'html[data-tamano="pequeno"]',
        'html[data-tamano="grande"]',
        'html[data-tamano="muy-grande"]',
        'html[data-fuente="dislexia"]',
        'html[data-fuente="legible"]',
        'html[data-contraste="alto"]',
        'html[data-movimiento="reducido"]',
    ):
        assert selector in css, selector
    # Las tipografías del panel apuntan a archivos que sí existen
    for fuente in re.findall(r"url\('\.\./(fonts/[^']+)'\)", css):
        assert finders.find(fuente), fuente


@pytest.mark.parametrize(
    "ruta",
    [
        "css/ajustes.css",
        "js/ajustes.js",
        # Pendiente: agregar "audio/ambiente.wav" cuando se suba el archivo de la música ambiental
        "fonts/opendyslexic-latin-400-normal.woff2",
        "fonts/opendyslexic-latin-700-normal.woff2",
        "fonts/atkinson-hyperlegible-latin-400-normal.woff2",
        "fonts/atkinson-hyperlegible-latin-700-normal.woff2",
    ],
)
def test_flujo_normal_archivos_estaticos_existen(ruta):
    """Recursos que necesita el panel: estilos, script y tipografías."""
    assert finders.find(ruta), f"Falta el archivo estático {ruta}"


# ---------------------------------------------------------------- flujo alternativo
def test_fa1_boton_restaurar_valores_por_defecto(client):
    """FA1: el panel ofrece la opción «Restaurar valores por defecto»."""
    html = client.get("/").content.decode()
    boton = re.search(r'<button[^>]*id="ajustes-restaurar"[^>]*>([^<]+)</button>', html)
    assert boton and boton.group(1).strip() == "Restaurar valores por defecto"


# ---------------------------------------------------------------- flujo de excepción
def test_fe1_area_de_aviso_para_errores_al_guardar(client):
    """FE1: existe el aviso donde se informa que los ajustes solo duran la sesión actual."""
    html = client.get("/").content.decode()
    aviso = re.search(r'<div[^>]*id="ajustes-aviso"[^>]*>', html).group(0)
    assert 'role="status"' in aviso and 'aria-live="polite"' in aviso
    assert " hidden" in aviso
    assert "solo se mantendrán durante la sesión actual" in _leer_estatico("js/ajustes.js")


# ---------------------------------------------------------------- regla de negocio
@pytest.mark.django_db
def test_rn04_ajustes_no_modifican_la_partida(client):
    """RN04: los ajustes son globales, viven en el navegador y no tocan el progreso del juego."""
    partida = _partida()
    antes = {c: getattr(partida, c) for c in ("hp", "xp", "indice", "decisiones", "estado")}

    html = client.get(f"/partida/{partida.id}/").content.decode()
    inicio = html.find('id="ajustes-root"')
    panel = html[inicio : html.find("</section>", inicio)]
    assert "<form" not in panel  # el panel no envía nada al servidor
    assert "no afectan tu partida" in panel
    client.get(f"/partida/{partida.id}/estado/")

    partida.refresh_from_db()
    assert {c: getattr(partida, c) for c in antes} == antes
    assert not any("ajuste" in clave for clave in client.session.keys())
