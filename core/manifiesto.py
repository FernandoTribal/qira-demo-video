"""Lo que la corrida entrega (§6, Anexo A.2): cuatro archivos DENTRO de
`reports/allure-results/`.

Adentro y no al lado: cinco corridas archivadas compartirían un único
`suite.json` —el de la última— y las otras cuatro se leerían con el ambiente y
el dispositivo de una corrida que no es la suya.

Lo escribe un hook del runner y no `run.sh` porque sólo el runner sabe cuántos
casos EXISTÍAN antes de filtrar. Y el mismo módulo escribe `suite.json` y
`environment.properties` porque los dos dicen el ambiente: si los escribieran
piezas distintas, el día que difieran no habría forma de saber cuál miente.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess

from core import config

DESTINO = config.RAIZ / "reports" / "allure-results"


def escribir(*, existentes: int, seleccionados: int, dispositivo: str) -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    base_ruta = config.RAIZ / "suite.base.json"
    # Sin la parte estática no se inventa: los campos quedan AUSENTES y quien
    # lee los reclama (principio 1). Se avisa por consola.
    base = json.loads(base_ruta.read_text(encoding="utf-8")) if base_ruta.is_file() else {}
    if not base:
        print("\n!! falta suite.base.json: el manifiesto sale sin proyecto, suite ni nivel")

    manifiesto = {
        **base,
        "ambiente": config.AMBIENTE,
        # De la corrida y no del archivo estático (§6.2.1): el humo y la
        # regresión salen de este mismo repo y sin esto son indistinguibles.
        "proposito": os.environ.get("PROPOSITO", "").strip().lower() or "sin declarar",
        "plataforma": config.PLATAFORMA,
        "casos_existentes": existentes,
        "casos_seleccionados": seleccionados,
        "build": config.BUILD,
        "dispositivo": dispositivo,
        "reporte_humano": (os.environ["BUILD_URL"] + "allure/"
                           if os.environ.get("BUILD_URL") else ""),
    }
    (DESTINO / "suite.json").write_text(
        json.dumps(manifiesto, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    (DESTINO / "environment.properties").write_text(
        f"ambiente={config.AMBIENTE}\n"
        f"plataforma={config.PLATAFORMA}\n"
        f"build={config.BUILD}\n"
        f"dispositivo={dispositivo}\n"
        f"rama={_git('rev-parse --abbrev-ref HEAD')}\n"
        f"commit={_git('rev-parse --short HEAD')}\n", encoding="utf-8")

    # Sin editar una línea (§6.4): es lo que hace que «problema de ambiente»
    # signifique lo mismo en todas las suites. Lo vigila `tests_unit`.
    shutil.copy(config.RAIZ / "allure-categories.json", DESTINO / "categories.json")

    # `executor.json`, en SINGULAR (§6.1, §13.10). Normalmente lo escribe el
    # plugin del CI; si no hay CI se deja uno mínimo para que el crudo esté
    # completo, y nunca se pisa el del CI.
    ejecutor = DESTINO / "executor.json"
    if not ejecutor.exists():
        ejecutor.write_text(json.dumps({
            "name": "Jenkins" if os.environ.get("BUILD_URL") else "local",
            "type": "jenkins" if os.environ.get("BUILD_URL") else "local",
            "buildName": os.environ.get("BUILD_TAG", ""),
            "buildUrl": os.environ.get("BUILD_URL", ""),
            "reportUrl": manifiesto["reporte_humano"],
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _git(orden: str) -> str:
    try:
        return subprocess.run(["git", *orden.split()], cwd=config.RAIZ,
                              capture_output=True, text=True,
                              timeout=10).stdout.strip() or "sin declarar"
    except (OSError, subprocess.SubprocessError):
        return "sin declarar"
