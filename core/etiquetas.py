"""Las etiquetas del §6.3, puestas AL COLECTAR y no al ejecutar (Anexo A.3).

Si el `caso_id` se asignara durante la ejecución, sólo lo recibirían los casos
que corren; los saltados llegarían sin ID ni título legible, y justo ésos son
los que hay que listar como «no ejecutados». Va como etiqueta Y como título: el
título se reescribe y se trunca; la etiqueta sobrevive.
"""
from __future__ import annotations

import re

import pytest

# `CP-…: título` al principio del docstring. Acepta `CP-01` y `CP-HUM-01`.
CASO_ID = re.compile(r"^\s*(CP(?:-[A-Z0-9]+)+)\s*:\s*(.+)")

# Marca → severidad (como la primera suite móvil de la casa). `@pytest.mark.severidad("…")` en el caso
# gana sobre esto. Traduce «fallaron 5» a «1 bloqueante y 4 menores».
SEVERIDAD_POR_MARCA = {
    "humo": "blocker",
}
SEVERIDADES = ("blocker", "critical", "normal", "minor", "trivial")


def del_docstring(funcion) -> tuple:
    """(caso_id, título) o ('', '') si el caso no lo declara."""
    m = CASO_ID.match((funcion.__doc__ or "").strip())
    return (m.group(1), m.group(2).strip()) if m else ("", "")


def severidad(item) -> str:
    explicita = item.get_closest_marker("severidad")
    if explicita and explicita.args:
        return explicita.args[0]
    for marca, valor in SEVERIDAD_POR_MARCA.items():
        if item.get_closest_marker(marca):
            return valor
    return ""


def etiquetar(item, sistemas: dict) -> None:
    """`sistemas` = {fixture: sistema}. Llega de `conftest` y no se importa de
    `data/`: `core/` no sabe de este producto, la flecha nunca sube."""
    caso_id, titulo = del_docstring(item.function)
    if caso_id:
        item.add_marker(pytest.mark.allure_label(caso_id, label_type="caso_id"))
        item.function.__allure_display_name__ = f"{caso_id}: {titulo}"

    nivel = severidad(item)
    if nivel:
        item.add_marker(pytest.mark.allure_label(nivel, label_type="severity"))

    # Los ejes se DERIVAN de las fixtures (§5.4): un caso que pide `app` ES de
    # la app, y nadie tiene que acordarse de marcarlo.
    for fixture, sistema in sistemas.items():
        if fixture in item.fixturenames:
            item.add_marker(pytest.mark.allure_label(sistema, label_type="tag"))

    for marca in item.iter_markers("func"):
        if marca.args:
            item.add_marker(pytest.mark.allure_label(marca.args[0], label_type="feature"))
