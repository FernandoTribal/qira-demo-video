"""Lo mínimo para saber si tiene sentido correr lo demás.

Un caso de humo no prueba una regla de negocio: prueba que la app está viva.
Por eso es `blocker` (lo pone la marca `humo`, ver `core/etiquetas.py`).
"""
from __future__ import annotations

import pytest

from screens.pantalla_inicio import PantallaInicio


@pytest.mark.humo
@pytest.mark.func("Arranque")
def test_la_app_abre_en_su_pantalla_inicial(app, v):
    """CP-HUM-01: la app abre en su pantalla inicial

    Si la app no llega a pintar su primera pantalla, todo lo que venga después
    mide sobre otra cosa.
    """
    inicio = PantallaInicio(app)
    inicio.aparece()
    v.cargada(inicio)
