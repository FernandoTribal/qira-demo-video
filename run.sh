#!/usr/bin/env bash
# El único atajo (§4, Anexo A.10). La máquina que ejecuta no sabe qué es pytest
# ni qué es Appium: sabe `./run.sh <suite>`.
#
#   ./run.sh [suite] [args de pytest]   humo | regresion (por omisión) | completa
#   ./run.sh --suites                   las suites que hay
#   ./run.sh --unitarias                la batería de coherencia, sin dispositivo
#   ./run.sh --preparar                 arma .venv e instala requirements.txt
#
#   PLATAFORMA=ios ./run.sh humo        contra un iPhone (por omisión, android)
#
# Códigos: 0 pasó · 1 falló algún caso · 2 no hubo corrida (suite o plataforma
# que no existe) · 3 no hubo corrida (faltaba el entorno de Python).
set -euo pipefail
cd "$(dirname "$0")"

# Duplicada de `data/suites.py` A PROPÓSITO: acá todavía puede no haber Python.
# Que no se separen lo vigila `tests_unit`.
SUITES_CONOCIDAS=" humo regresion completa "
VENV=".venv"
PY="$VENV/bin/python"

preparar() {
  echo ">> Armando el entorno de Python en ${VENV}…"
  "${PYTHON:-python3}" -m venv "$VENV"
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet -r requirements.txt
}

asegurar_entorno() {
  if [[ ! -x "$PY" ]]; then
    preparar || { echo "!! No pude armar ${VENV}." >&2; exit 3; }
  fi
}

# ── Lo que no produce resultados: va ANTES de la limpieza y sale por acá ────
case "${1:-}" in
  --suites)
    echo "Las suites de este proyecto:"
    echo "  humo        lo mínimo para saber si la app está viva"
    echo "  regresion   todo lo que NO deja rastro real (por omisión)"
    echo "  completa    todo; lo que escribe igual pide --efectos"
    exit 0 ;;
  --preparar)
    preparar; exit 0 ;;
  --unitarias)
    shift; asegurar_entorno
    # Sin `addopts`: sin --alluredir, así la batería no deja crudo que alguien
    # pueda confundir con una corrida.
    exec "$PY" -m pytest tests_unit -q -p no:cacheprovider -o addopts= "$@" ;;
esac

# ── La suite. Una que no existe NO es una corrida vacía: es un error de quien
# llamó, y se dice ANTES de borrar nada. ─────────────────────────────────────
SUITE="regresion"
if [[ $# -gt 0 && "$1" != -* ]]; then
  SUITE="$1"; shift
fi
if [[ "$SUITES_CONOCIDAS" != *" $SUITE "* ]]; then
  echo "No existe la suite '$SUITE'. Hay:$SUITES_CONOCIDAS" >&2
  exit 2
fi

# Se EXPORTA para que `core/config.py` lea lo mismo que decide este script: si
# no coincidieran, se correría en un aparato y se entregaría como el otro.
export PLATAFORMA="${PLATAFORMA:-android}"
if [[ "$PLATAFORMA" != "android" && "$PLATAFORMA" != "ios" ]]; then
  echo "Plataforma desconocida: '$PLATAFORMA'. Hay: android ios" >&2
  exit 2
fi

asegurar_entorno

# ── La limpieza no es higiene: es corrección (§6.1). Si quedaran los resultados
# de ayer, quien lee contaría casos que hoy no corrieron. ─────────────────────
rm -rf reports/allure-results reports/junit.xml
mkdir -p reports/allure-results

# Appium NO se levanta acá: si no responde, la guarda de `conftest.py` salta
# todo con `ambiente:` y la corrida lo dice, en vez de N defectos de producto.
# `"$@"` al final es lo que hace que el `EXTRA` de la receta funcione.
exec "$PY" -m pytest --suite "$SUITE" "$@"
