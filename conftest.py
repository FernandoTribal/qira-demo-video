"""Las fixtures: el estado se declara, nunca se prepara (§5.4).

Un caso dice en su firma qué necesita —`def test_x(app, v)`— y una fixture lo
garantiza. Ningún caso toca el driver.

El módulo de ajustes se importa como `ajustes` y no como `config`: `config` es
el parámetro que pytest pasa a sus hooks, y con el mismo nombre uno tapa al
otro de una forma que sólo se nota cuando algo ya falló.
"""
from __future__ import annotations

import pytest

from core import config as ajustes
from core import driver, etiquetas, evidencia, manifiesto
from core.verify import Verify
from data.suites import SUITES, sistema_por_fixture

# Lo que QIRA deja en `borradores/qira/` NUNCA corre: son borradores para que
# una persona los lea y los pase a `tests/`. `testpaths` y `norecursedirs` ya lo
# impiden; esto cubre también a quien nombre la carpeta a mano.
collect_ignore_glob = ["borradores/*"]

# La guarda de ambiente se evalúa UNA vez por corrida, no una por caso.
_AMBIENTE: dict = {}


def pytest_addoption(parser) -> None:
    parser.addoption("--suite", default="", help="una suite con nombre (data/suites.py)")
    parser.addoption("--efectos", action="store_true",
                     help="deja correr los casos que ESCRIBEN en el producto (§5.5)")


# ── La colección: contar, etiquetar y filtrar, en ese orden ────────────────

@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items) -> None:
    # PRIMERO contar, antes de que ningún filtro recorte: «30 de 30 en verde»
    # oculta que había 40.
    config._existentes = len(items)

    # Etiquetar ACÁ: un caso saltado tiene que llegar con su `caso_id`.
    sistemas = sistema_por_fixture()
    for item in items:
        etiquetas.etiquetar(item, sistemas)

    suite = config.getoption("--suite")
    if suite:
        if suite not in SUITES:
            raise pytest.UsageError(f"suite desconocida: {suite!r}. Hay: {', '.join(SUITES)}")
        expresion = SUITES[suite]
        if expresion:
            actual = config.option.markexpr
            config.option.markexpr = f"({actual}) and ({expresion})" if actual else expresion


def _motivo_de_ambiente() -> str:
    """Vacío si se puede correr; si no, el motivo con `ambiente:` (§6.4).

    Se pregunta ANTES del primer caso, cuando todavía se puede distinguir una
    caída de un defecto. Después, los dos son «no pasó».
    """
    if "motivo" not in _AMBIENTE:
        faltan = ajustes.faltantes()
        if faltan:
            motivo = f"ambiente: faltan variables para abrir la app: {', '.join(faltan)}"
        else:
            motivo = driver.appium_no_responde()
        if not motivo and ajustes.url_declarada():
            motivo = _url_no_responde(ajustes.url())
        _AMBIENTE["motivo"] = motivo
    return _AMBIENTE["motivo"]


def _url_no_responde(url: str) -> str:
    """Petición pelada; un 5xx también es caída (§6.4)."""
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            codigo = r.status
    except urllib.error.HTTPError as e:
        codigo = e.code
    except Exception as e:
        return f"ambiente: {url} no contesta ({type(e).__name__})"
    return f"ambiente: {url} contestó {codigo}" if codigo >= 500 else ""


# ── Las fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def v(request):
    """El objeto de verificación, y la puerta por la que pasan TODOS los casos.

    Por eso la guarda de ambiente se engancha acá, y `tests_unit` falla si un
    caso no lo pide. `volcar()` lo llama esta fixture, pase lo que pase.
    """
    motivo = _motivo_de_ambiente()
    if motivo:
        pytest.skip(motivo)
    capturar = (lambda _que: request.getfixturevalue("app").captura()
                if "app" in request.fixturenames else None)
    verificador = Verify(capturar=capturar)
    yield verificador
    verificador.volcar()


@pytest.fixture(scope="session")
def _driver():
    """Uno por corrida: abrir la sesión cuesta segundos.

    La guarda se repite acá porque pytest arma las fixtures de sesión ANTES que
    `v`: sin esto, un Appium caído saldría como error del caso y no como salto.
    """
    motivo = _motivo_de_ambiente()
    if motivo:
        pytest.skip(motivo)
    d = driver.abrir()
    yield d
    d.quit()


@pytest.fixture
def app(_driver, request):
    """La app recién abierta. Declara el sistema `app-<plataforma>`.

    También es donde empieza la evidencia: se graba la pantalla mientras la
    app está en uso y la sesión queda a mano del hook que adjunta al fallar.
    Acá y no en cada caso: un caso no toca el driver.
    """
    sesion = driver.Sesion(_driver)
    with evidencia.del_caso(request.node, sesion):
        sesion.reiniciar_app()
        yield sesion


@pytest.fixture
def sin_sesion(app):
    """La app sin sesión abierta: el Login es la primera pantalla real.

    Un caso que inicia sesión la deja abierta y `no_reset` la conserva hasta
    la corrida siguiente. Se declara acá y no se «cierra sesión» al final del
    caso: si el caso falla a la mitad, la limpieza no corre.
    """
    # En el simulador de iOS se puede; en un iPhone real no (ver `borrar_datos`).
    if not app.borrar_datos():
        pytest.skip("ambiente: en un iPhone real no hay cómo borrar los datos de la app")
    return app


@pytest.fixture
def efectos(request):
    """Todo caso marcado `@pytest.mark.efectos` la pide; `tests_unit` lo vigila.

    Una casilla en la receta que no está cableada a nada es peor que no tenerla
    (§13.9): quien la deja sin marcar cree que detuvo algo.
    """
    if not request.config.getoption("--efectos"):
        pytest.skip("deliberado: este caso ESCRIBE en el producto. Se corre con --efectos.")


# ── La evidencia de lo que falló (core/evidencia.py) ───────────────────────

@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    """En cada fase (preparar, correr, cerrar), DESPUÉS de que pytest armó el
    reporte: así se sabe si falló, y la pantalla todavía es la del fallo
    (el cierre de las fixtures viene después). Nunca cambia el reporte."""
    reporte = yield
    evidencia.al_reportar(item, call, reporte)
    return reporte


# ── El cierre: el manifiesto (§6) ──────────────────────────────────────────

def pytest_sessionfinish(session, exitstatus) -> None:
    # Sólo una corrida de verdad entrega: ni `--collect-only` ni la batería de
    # coherencia (que corre sin `--alluredir`) producen resultados que contar.
    if session.config.option.collectonly or not session.config.getoption(
            "allure_report_dir", default=None):
        return
    manifiesto.escribir(
        existentes=getattr(session.config, "_existentes", session.testscollected),
        seleccionados=session.testscollected,
        dispositivo=driver.DISPOSITIVO["descripcion"],
    )
