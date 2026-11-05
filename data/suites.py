"""Las suites con nombre y los sistemas que se derivan de las fixtures.

La lista de suites está también en `run.sh` y en `ci/Jenkinsfile`, A PROPÓSITO
(§13.7): cada uno la necesita antes de que exista el anterior (`run.sh` antes de
que haya un Python; la receta antes de clonar). Duplicar sin vigilancia es
deuda; `tests_unit` falla si las tres listas se separan.
"""
from __future__ import annotations

# Nombre → expresión de marcadores para `-m`. Vacía = todo.
SUITES = {
    # Lo mínimo para saber si tiene sentido correr lo demás.
    "humo": "humo",
    # Todo lo que NO deja rastro real en el producto (§5.5).
    "regresion": "not efectos",
    # Todo, incluido lo que escribe. Lo que escribe igual pide `--efectos`.
    "completa": "",
}

# La opción que NO corre nada y va PRIMERA en la receta (§8): se lleva el
# «Construir ahora» de un trabajo recién creado. No es una suite y no va arriba.
DESPERTAR = "despertar"


def sistema_por_fixture() -> dict:
    """Fixture → sistema declarado en `suite.base.json` → `sistemas`.

    Una función y no un diccionario: la plataforma se decide en el entorno y un
    diccionario se congelaría al importar. Un caso que pide `app` es de la app
    de ESA plataforma sin que nadie lo marque.
    """
    from core import config

    return {"app": f"app-{config.PLATAFORMA}"}
