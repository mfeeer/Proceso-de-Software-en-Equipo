"""CU03 - Personalizar interfaz: el engranaje de ajustes debe estar en todas las pantallas."""

import pytest
from django.contrib.staticfiles import finders


def test_home_incluye_engranaje_y_recursos(client):
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


@pytest.mark.parametrize(
    "ruta",
    [
        "css/ajustes.css",
        "js/ajustes.js",
        "audio/ambiente.wav",
        "fonts/opendyslexic-latin-400-normal.woff2",
        "fonts/opendyslexic-latin-700-normal.woff2",
        "fonts/atkinson-hyperlegible-latin-400-normal.woff2",
        "fonts/atkinson-hyperlegible-latin-700-normal.woff2",
    ],
)
def test_archivos_estaticos_existen(ruta):
    assert finders.find(ruta), f"Falta el archivo estático {ruta}"
