"""La evidencia de un caso que falla: captura, árbol de la pantalla y video.

Ningún caso la pide ni la llama. La toma la infraestructura: la fixture `app`
graba y registra la sesión, y el hook `pytest_runtest_makereport` de
`conftest.py` adjunta al reporte. Si dependiera de que cada caso se acuerde, el
día que hace falta —un rojo de madrugada en QORA que nadie vio— no estaría.

Por qué hace falta además de lo que ya adjunta `v`: `core/verify.py` captura en
el momento de una verificación que falla, pero un caso que se cae por una
excepción (un elemento que no aparece, un timeout, un dato que falta en el
`.env`) no pasa por `v` y llegaba al reporte con la traza y nada más.

Tres reglas que no se negocian:

- **Nunca tapa el error original.** Todo va envuelto: si la sesión murió, si
  Appium no graba, si Allure no está, se pierde evidencia y el caso falla por
  lo que falló, no por esto.
- **No repite lo que `v` ya adjuntó.** Una verificación que falla trae su
  captura del momento; una segunda, tomada después, muestra otra pantalla y
  confunde.
- **Una vez por caso**, en la primera fase que falla: es la más cercana a lo
  que pasó. Un cierre que falla después de un caso caído es consecuencia.
"""
from __future__ import annotations

import warnings
from contextlib import contextmanager

import pytest

from core import config
from core.verify import FalloCritico, FallosAcumulados

try:  # §7: el reporte es opcional; la suite corre igual sin él
    import allure
    from allure_commons.types import AttachmentType
except ImportError:  # pragma: no cover
    allure = None

# Un caso móvil dura uno o dos minutos; el fallo suele estar al FINAL. Con los
# 180 s que Appium usa por omisión, un caso largo perdería justo el momento que
# importa; más de 10 minutos es otra cosa (un caso colgado) y el video pesaría
# decenas de megas. 600 entra en el máximo de UiAutomator2 (1800) y de XCUITest.
LIMITE_VIDEO_S = 600

# Lo que el hook necesita del caso, guardado EN el caso y no en globales: con
# reintentos (`--reruns`) el mismo caso corre dos veces y cada intento tiene lo
# suyo.
_SESION = pytest.StashKey[object]()
_VIDEO = pytest.StashKey[object]()
_FALLO_LA_FASE = pytest.StashKey[dict]()

# Lo que se dice una sola vez por corrida, no una por caso.
_DICHO: set = set()
# Si Appium no pudo grabar una vez (en iOS, falta `ffmpeg` en la máquina de
# Appium), no se reintenta en cada caso: sería pagar el intento N veces para
# leer N veces el mismo aviso.
_SIN_VIDEO = {"motivo": ""}


class SinVideo(UserWarning):
    """Aparece en el resumen de avisos de pytest, en la consola del CI."""


def modo_video() -> str:
    """`fallos` (por omisión), `siempre` o `nunca`.

    Un valor que no se entiende cae en `fallos` y se avisa: la evidencia es un
    extra, y una errata en `.env` no puede parar una corrida.
    """
    if config.EVIDENCIA_VIDEO in config.MODOS_DE_VIDEO:
        return config.EVIDENCIA_VIDEO
    _avisar_una_vez(f"EVIDENCIA_VIDEO={config.EVIDENCIA_VIDEO!r} no se entiende "
                    f"(hay: {', '.join(config.MODOS_DE_VIDEO)}); se usa «fallos»")
    return "fallos"


# ── La fixture `app`: registrar la sesión y grabar ─────────────────────────

@contextmanager
def del_caso(item, sesion):
    """Envuelve la vida de la app en un caso: graba desde que abre hasta que
    se cierra, y deja la sesión a mano del hook.

    Va como `with` alrededor del `yield` de la fixture: si la app no llega a
    abrir, el `finally` igual detiene la grabación (y el video de ese arranque
    fallido es justo el que sirve).
    """
    item.stash[_SESION] = sesion
    item.stash[_VIDEO] = None
    grabando = _empezar_video(sesion)
    try:
        yield
    finally:
        if grabando:
            item.stash[_VIDEO] = _terminar_video(sesion)


def _empezar_video(sesion) -> bool:
    if modo_video() == "nunca" or _SIN_VIDEO["motivo"]:
        return False
    try:
        sesion.empezar_grabacion(LIMITE_VIDEO_S)
        return True
    except Exception as e:
        primera_linea = (str(e).strip().splitlines() or [""])[0]
        _SIN_VIDEO["motivo"] = f"{type(e).__name__}: {primera_linea}"
        _avisar_una_vez(
            f"no se pudo grabar la pantalla ({_SIN_VIDEO['motivo']}); la corrida "
            f"sigue SIN video. En iOS, la máquina de Appium necesita ffmpeg")
        return False


def _terminar_video(sesion):
    try:
        return sesion.terminar_grabacion()
    except Exception:
        return None  # se pierde el video; no se inventa un fallo


# ── El hook: adjuntar ──────────────────────────────────────────────────────

def al_reportar(item, call, reporte) -> None:
    """Lo llama `pytest_runtest_makereport` en cada fase. Nunca lanza."""
    try:
        _al_reportar(item, call, reporte)
    except Exception:
        pass  # la evidencia nunca tapa el error original


def _al_reportar(item, call, reporte) -> None:
    if reporte.when == "setup":
        # Un intento nuevo (o el primero): lo del anterior no cuenta. El video
        # NO se limpia acá: si la app no abrió, ya está guardado y es el que sirve.
        item.stash[_FALLO_LA_FASE] = {}
    fases = item.stash.setdefault(_FALLO_LA_FASE, {})
    primera = reporte.failed and not any(fases.values())
    fases[reporte.when] = reporte.failed

    if primera:
        _adjuntar_pantalla(item, call.excinfo.value if call.excinfo else None)
    if reporte.when == "teardown":
        _adjuntar_video(item, fallo=any(fases.values()))
        # Con un reintento, el intento siguiente registra la suya de nuevo.
        item.stash[_SESION] = None


def _adjuntar_pantalla(item, error) -> None:
    sesion = item.stash.get(_SESION, None)
    if sesion is None:
        return  # el caso no abrió la app, o no llegó a abrirla: no hay qué mirar
    if isinstance(error, FallosAcumulados):
        return  # cada verificación que falló ya trajo su captura del momento
    if not isinstance(error, FalloCritico):  # el crítico también trae la suya
        imagen = sesion.captura()
        if imagen:
            _adjuntar(imagen, "captura al fallar", "PNG")
    # El árbol responde lo que la captura no: si el elemento que no apareció
    # estaba con otro texto, otro id o tapado. Para un crítico («la pantalla no
    # es la que el caso cree») es lo más útil que hay.
    try:
        arbol = sesion.fuente()
    except Exception:
        arbol = ""
    if arbol:
        _adjuntar(arbol.encode("utf-8"), "árbol de la pantalla", "XML")


def _adjuntar_video(item, fallo: bool) -> None:
    video = item.stash.get(_VIDEO, None)
    item.stash[_VIDEO] = None  # no retener megas hasta el final de la corrida
    if video and (fallo or modo_video() == "siempre"):
        _adjuntar(video, "video", "MP4")


def _adjuntar(cuerpo: bytes, nombre: str, tipo: str) -> None:
    if allure is not None:
        allure.attach(cuerpo, name=nombre, attachment_type=getattr(AttachmentType, tipo))


def _avisar_una_vez(mensaje: str) -> None:
    if mensaje not in _DICHO:
        _DICHO.add(mensaje)
        warnings.warn(mensaje, SinVideo, stacklevel=2)
