"""La evidencia de un caso que falla (`core/evidencia.py` y su hook), con dobles.

Sin Appium ni teléfono: una sesión de mentira que cuenta lo que le piden. Lo
que se vigila es lo que le importa a quien abre el reporte de un rojo: que
haya con qué entenderlo, que no se repita lo que `v` ya adjuntó, y que nada de
esto tape el error original ni haga fallar un caso.
"""
from __future__ import annotations

import base64
import importlib

import pytest

from core import config, evidencia
from core.verify import FalloCritico, FallosAcumulados

PNG = b"\x89PNG-de-mentira"
MP4 = b"mp4-de-mentira"


class SesionDoble:
    def __init__(self, *, sin_pantalla=False, sin_grabar=False):
        self.sin_pantalla = sin_pantalla
        self.sin_grabar = sin_grabar
        self.grabaciones = 0
        self.terminadas = 0

    def captura(self):
        return None if self.sin_pantalla else PNG

    def fuente(self):
        if self.sin_pantalla:
            raise RuntimeError("la sesión murió")
        return "<arbol><boton texto='Ingresa'/></arbol>"

    def empezar_grabacion(self, limite_s):
        assert limite_s == evidencia.LIMITE_VIDEO_S
        if self.sin_grabar:
            raise RuntimeError("ffmpeg no está instalado\nmás detalle")
        self.grabaciones += 1

    def terminar_grabacion(self):
        self.terminadas += 1
        return MP4


class Caso:
    def __init__(self):
        self.stash = pytest.Stash()


class Reporte:
    def __init__(self, when, failed=False):
        self.when, self.failed = when, failed


class Llamada:
    def __init__(self, error=None):
        self.excinfo = type("Excinfo", (), {"value": error})() if error else None


@pytest.fixture
def adjuntos(monkeypatch):
    """Lo que habría ido a Allure, como (nombre, tipo)."""
    hechos = []
    monkeypatch.setattr(evidencia, "_adjuntar",
                        lambda cuerpo, nombre, tipo: hechos.append((nombre, tipo)))
    monkeypatch.setattr(config, "EVIDENCIA_VIDEO", "fallos")
    monkeypatch.setitem(evidencia._SIN_VIDEO, "motivo", "")
    monkeypatch.setattr(evidencia, "_DICHO", set())
    return hechos


def correr(sesion, *, setup=None, call=None, teardown=None, abre=True):
    """Un caso entero, en el orden de pytest: la fixture `app` abre (y empieza
    a grabar), reporte de la preparación, reporte del caso, la fixture cierra
    (y guarda el video), reporte del cierre. Cada fase recibe la excepción con
    la que falla, o None si pasa."""
    caso = Caso()
    vida = evidencia.del_caso(caso, sesion) if sesion is not None else None
    if vida is not None:
        vida.__enter__()
        if not abre:  # la app no abrió: el `with` sale por excepción ya en la preparación
            setup = setup or RuntimeError("la app no abrió")
            vida.__exit__(RuntimeError, setup, None)
            vida = None

    def reportar(fase, error):
        evidencia.al_reportar(caso, Llamada(error), Reporte(fase, failed=error is not None))

    reportar("setup", setup)
    if setup is None:
        reportar("call", call)
    if vida is not None:
        vida.__exit__(None, None, None)
    reportar("teardown", teardown)
    return caso


# ── Lo que se adjunta ──────────────────────────────────────────────────────

def test_un_caso_que_se_cae_por_una_excepcion_deja_captura_arbol_y_video(adjuntos):
    """Evita el rojo sin evidencia: el caso que no pasa por `v` (un elemento
    que no aparece, un timeout) llegaba con la traza y nada más."""
    correr(SesionDoble(), call=TimeoutError("no apareció «Ingresa»"))
    assert adjuntos == [("captura al fallar", "PNG"),
                        ("árbol de la pantalla", "XML"),
                        ("video", "MP4")]


def test_un_caso_verde_no_adjunta_nada_pero_igual_cierra_la_grabacion(adjuntos):
    """Evita un reporte de megas en verde, y una grabación que queda abierta."""
    sesion = SesionDoble()
    correr(sesion)
    assert adjuntos == []
    assert (sesion.grabaciones, sesion.terminadas) == (1, 1)


def test_si_falla_al_preparar_tambien_hay_evidencia(adjuntos):
    """Evita perder justo el video de una app que no llegó a abrir."""
    sesion = SesionDoble()
    correr(sesion, abre=False)
    assert sesion.terminadas == 1
    assert adjuntos == [("captura al fallar", "PNG"),
                        ("árbol de la pantalla", "XML"),
                        ("video", "MP4")]


def test_no_repite_la_captura_de_las_verificaciones_de_v(adjuntos):
    """Evita una segunda captura tomada al cerrar, que muestra otra pantalla
    que la del momento en que la verificación falló."""
    correr(SesionDoble(), teardown=FallosAcumulados("1 verificaciones fallaron"))
    assert adjuntos == [("video", "MP4")]


def test_un_critico_suma_el_arbol_pero_no_otra_captura(adjuntos):
    """El crítico ya trae la suya; el árbol dice por qué la pantalla no es la
    que el caso cree."""
    correr(SesionDoble(), call=FalloCritico("la pantalla «Login» está cargada"))
    assert adjuntos == [("árbol de la pantalla", "XML"), ("video", "MP4")]


def test_la_evidencia_es_de_la_primera_fase_que_falla(adjuntos):
    """Un cierre que falla después de un caso caído es consecuencia: dos
    juegos de capturas confunden en vez de explicar."""
    correr(SesionDoble(), call=TimeoutError("x"), teardown=RuntimeError("y"))
    assert [n for n, _ in adjuntos].count("captura al fallar") == 1


def test_un_caso_saltado_no_es_un_fallo(adjuntos):
    """Evita adjuntar evidencia a un `ambiente:` que nunca llegó a correr."""
    caso = Caso()
    evidencia.al_reportar(caso, Llamada(pytest.skip.Exception("ambiente: x")),
                          Reporte("setup", failed=False))
    evidencia.al_reportar(caso, Llamada(), Reporte("teardown"))
    assert adjuntos == []


# ── El video, según EVIDENCIA_VIDEO ────────────────────────────────────────

def test_siempre_adjunta_el_video_tambien_en_verde(adjuntos, monkeypatch):
    monkeypatch.setattr(config, "EVIDENCIA_VIDEO", "siempre")
    correr(SesionDoble())
    assert adjuntos == [("video", "MP4")]


def test_nunca_no_graba(adjuntos, monkeypatch):
    """Evita pagar la grabación en cada caso cuando se pidió que no."""
    monkeypatch.setattr(config, "EVIDENCIA_VIDEO", "nunca")
    sesion = SesionDoble()
    correr(sesion, call=TimeoutError("x"))
    assert sesion.grabaciones == 0
    assert ("video", "MP4") not in adjuntos
    assert ("captura al fallar", "PNG") in adjuntos


def test_un_valor_raro_cae_en_fallos_y_avisa(adjuntos, monkeypatch):
    monkeypatch.setattr(config, "EVIDENCIA_VIDEO", "siempe")
    with pytest.warns(evidencia.SinVideo, match="siempe"):
        assert evidencia.modo_video() == "fallos"


def test_si_no_se_puede_grabar_sigue_sin_video_y_lo_dice_una_vez(adjuntos):
    """Evita que un iOS sin ffmpeg haga fallar casos, o llene la consola con
    el mismo aviso por cada caso."""
    with pytest.warns(evidencia.SinVideo, match="ffmpeg no está instalado") as avisos:
        sin_grabar = SesionDoble(sin_grabar=True)
        correr(sin_grabar, call=TimeoutError("x"))
        otra = SesionDoble()
        correr(otra, call=TimeoutError("x"))
    assert len(avisos) == 1
    assert otra.grabaciones == 0  # no se reintenta en cada caso
    assert ("video", "MP4") not in adjuntos
    assert ("captura al fallar", "PNG") in adjuntos


# ── Lo que nunca tiene que pasar ───────────────────────────────────────────

def test_sin_app_no_adjunta_nada_y_no_lanza(adjuntos):
    """Un caso que no abre la app (o que falló antes de abrirla) no tiene
    pantalla que mostrar."""
    correr(None, setup=RuntimeError("faltan variables"))
    assert adjuntos == []


def test_una_sesion_muerta_no_tapa_el_error_original(adjuntos):
    correr(SesionDoble(sin_pantalla=True), call=TimeoutError("x"))
    assert ("captura al fallar", "PNG") not in adjuntos


def test_un_error_adentro_de_la_evidencia_no_sale(adjuntos, monkeypatch):
    def revienta(*_):
        raise RuntimeError("bug en la evidencia")
    monkeypatch.setattr(evidencia, "_al_reportar", revienta)
    evidencia.al_reportar(Caso(), Llamada(TimeoutError("x")), Reporte("call", True))


# ── El enganche: lo hace la infraestructura, no el caso ────────────────────

def test_el_hook_de_conftest_delega_y_devuelve_el_mismo_reporte(adjuntos):
    """Evita un hook que se come el reporte (pytest perdería el resultado) o
    que no llama a la evidencia (todo lo de arriba no correría nunca)."""
    conftest = importlib.import_module("conftest")
    caso, reporte = Caso(), Reporte("call", failed=True)
    with evidencia.del_caso(caso, SesionDoble()):
        hook = conftest.pytest_runtest_makereport(caso, Llamada(TimeoutError("x")))
        next(hook)
        with pytest.raises(StopIteration) as fin:
            hook.send(reporte)
    assert fin.value.value is reporte
    assert ("captura al fallar", "PNG") in adjuntos


@pytest.mark.parametrize("plataforma, esperadas", [
    ("android", {"timeLimit", "forceRestart"}),
    ("ios", {"timeLimit", "forceRestart", "videoType", "pixelFormat"}),
])
def test_la_sesion_graba_en_un_formato_que_el_navegador_reproduce(monkeypatch, plataforma,
                                                                  esperadas):
    """En iOS, el mjpeg que XCUITest usa por omisión no se ve en el reporte."""
    from core import driver

    class DriverDoble:
        def start_recording_screen(self, **opciones):
            self.opciones = opciones

        def stop_recording_screen(self):
            return base64.b64encode(MP4).decode()

    monkeypatch.setattr(config, "ES_IOS", plataforma == "ios")
    doble = DriverDoble()
    sesion = driver.Sesion(doble)
    sesion.empezar_grabacion(evidencia.LIMITE_VIDEO_S)
    assert set(doble.opciones) == esperadas
    assert doble.opciones["timeLimit"] == evidencia.LIMITE_VIDEO_S
    if plataforma == "ios":
        assert doble.opciones["videoType"] == "libx264"
    assert sesion.terminar_grabacion() == MP4
