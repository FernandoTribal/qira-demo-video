"""El dueño de la sesión de Appium. Nadie más arriba toca el driver.

Android (UiAutomator2) o iOS (XCUITest), según `PLATAFORMA`. Se prueba el
mismo binario que se libera —también si la app es Flutter (§3.2)—: nada de
builds de depuración con extensiones compiladas.
"""
from __future__ import annotations

import base64
import json
import urllib.request

from core import config

# Lo que se sabe del aparato después de abrir la sesión. Va al manifiesto: un
# fallo que sólo pasa en un teléfono chico es otra historia sin el modelo.
DISPOSITIVO = {"descripcion": "sin declarar"}


def appium_no_responde() -> str:
    """Vacío si Appium contesta; si no, el motivo con su prefijo (§6.4).

    Petición pelada a `/status`, sin abrir sesión: lo que se quiere saber es si
    hay servidor, no si la app arranca. Sin esto, un Appium caído entra al
    tablero como N defectos de producto.
    """
    try:
        with urllib.request.urlopen(f"{config.APPIUM_URL}/status", timeout=5) as r:
            if r.status >= 500:
                return f"ambiente: Appium en {config.APPIUM_URL} contestó {r.status}"
            json.load(r)
    except Exception as e:  # red, conexión rechazada, respuesta que no es Appium
        return (f"ambiente: Appium no responde en {config.APPIUM_URL} "
                f"({type(e).__name__}). No se corrió nada contra un servidor caído")
    return ""


def abrir():
    from appium import webdriver

    driver = webdriver.Remote(config.APPIUM_URL,
                              options=_opciones_ios() if config.ES_IOS else _opciones_android())
    caps = driver.capabilities or {}
    modelo = caps.get("deviceModel") or caps.get("deviceName") or ""
    version = caps.get("platformVersion") or ""
    if modelo:
        DISPOSITIVO["descripcion"] = (
            f"{modelo} / {'iOS' if config.ES_IOS else 'Android'} {version}".strip())
    return driver


def _opciones_android():
    from appium.options.android import UiAutomator2Options

    o = UiAutomator2Options()
    o.app_package = config.PAQUETE
    o.app_activity = config.ACTIVIDAD
    if config.APK:
        o.app = config.APK
    # El estado lo declaran las fixtures, no el driver: reinstalar por caso
    # multiplicaría la corrida y escondería lo que el caso pidió.
    o.no_reset = True
    # Sin esto, en un equipo recién instalado los diálogos del sistema tapan la
    # primera pantalla y el rojo culpa a la app.
    o.auto_grant_permissions = True
    o.new_command_timeout = 300
    if config.ANDROID_UDID:
        o.udid = config.ANDROID_UDID
    return o


def _opciones_ios():
    """Sin `autoAcceptAlerts`, a propósito: acepta TODO diálogo, también los de
    la app que un caso tiene que poder leer, y el caso pasa sin mirar nada."""
    from appium.options.ios import XCUITestOptions

    o = XCUITestOptions()
    o.bundle_id = config.BUNDLE_ID
    if config.IPA:
        o.app = config.IPA
    o.no_reset = True
    o.new_command_timeout = 300
    if config.IOS_UDID:
        o.udid = config.IOS_UDID
    return o


class Sesion:
    """Lo que las pantallas pueden pedirle al dispositivo. Nada más."""

    def __init__(self, driver) -> None:
        self._driver = driver

    def fuente(self) -> str:
        """El árbol completo, de una vez (§5.1)."""
        return self._driver.page_source

    def en_primer_plano(self) -> bool:
        # 4 = corriendo en primer plano, igual en las dos plataformas.
        ident = config.BUNDLE_ID if config.ES_IOS else config.PAQUETE
        return self._driver.query_app_state(ident) == 4

    def reiniciar_app(self) -> None:
        """Cada caso arranca de la app recién abierta (§13.5): el estado que
        deja un caso es la fuente número uno de rojos que no significan nada."""
        ident = config.BUNDLE_ID if config.ES_IOS else config.PAQUETE
        self._driver.terminate_app(ident)
        self._driver.activate_app(ident)

    def borrar_datos(self) -> bool:
        """La app como recién instalada: sin sesión, sin tutorial visto.

        `no_reset` conserva la sesión entre corridas, así que un caso que
        inicia sesión deja la app en Inicio y el siguiente que espera el Login
        no lo encuentra nunca. Medido en QORA el 2026-10-26: la suite pasó 5/5
        una vez y 1/5 la siguiente. En iOS, `clearApp` existe para el
        simulador y no para un iPhone real: ahí devuelve `False` y quien lo
        pidió decide (la fixture `sin_sesion` salta el caso con `ambiente:`).

        Borrar también REVOCA los permisos que `auto_grant_permissions` dio al
        instalar, y el diálogo de notificaciones del sistema vuelve. Se
        conceden de nuevo antes de abrir: así queda igual que recién instalada,
        que es el estado contra el que se construyó el flujo de login."""
        if config.ES_IOS:
            from selenium.common.exceptions import WebDriverException
            try:
                self._driver.execute_script("mobile: clearApp", {"bundleId": config.BUNDLE_ID})
            except WebDriverException:
                # Un iPhone real: XCUITest no puede vaciar el contenedor de la app.
                return False
            self._driver.activate_app(config.BUNDLE_ID)
            return True
        self._driver.execute_script("mobile: clearApp", {"appId": config.PAQUETE})
        self._driver.execute_script("mobile: changePermissions", {
            "permissions": "all", "appPackage": config.PAQUETE, "action": "grant"})
        self._driver.activate_app(config.PAQUETE)
        return True

    def tocar(self, x: int, y: int) -> None:
        self._driver.tap([(x, y)])

    def escribir(self, texto: str) -> None:
        """Escribe en el campo que tiene el foco (se toca antes, desde la
        pantalla). Verificado contra la app real (§11 fase 2): `mobile: type`
        no deja texto en un `EditText` de Flutter en este build; el elemento
        con foco sí lo recibe."""
        self._driver.switch_to.active_element.send_keys(texto)

    def ocultar_teclado(self) -> None:
        """El teclado tapa el botón que sigue (Anexo A) y nadie lo pidió:
        se oculta siempre después de escribir, y no falla si ya no está."""
        try:
            self._driver.hide_keyboard()
        except Exception:
            pass

    def captura(self) -> bytes | None:
        try:
            return self._driver.get_screenshot_as_png()
        except Exception:
            return None  # se pierde evidencia; no se inventa un fallo

    def empezar_grabacion(self, limite_s: int) -> None:
        """Graba la pantalla hasta `terminar_grabacion()` o `limite_s`.

        `forceRestart`: si una corrida anterior quedó cortada con una grabación
        abierta, se descarta en vez de devolver aquel video como si fuera éste.
        En iOS lo graba `ffmpeg` en la máquina de Appium: el formato que
        XCUITest usa por omisión (mjpeg) no se reproduce en el navegador, y el
        reporte de Allure se mira en un navegador; H.264 en yuv420p sí."""
        opciones = {"timeLimit": limite_s, "forceRestart": True}
        if config.ES_IOS:
            opciones.update(videoType="libx264", pixelFormat="yuv420p")
        self._driver.start_recording_screen(**opciones)

    def terminar_grabacion(self) -> bytes | None:
        """El mp4 grabado desde `empezar_grabacion()`, o `None` si no hay."""
        crudo = self._driver.stop_recording_screen()
        return base64.b64decode(crudo) if crudo else None
