"""El dueño de la sesión de Appium. Nadie más arriba toca el driver.

Android (UiAutomator2) o iOS (XCUITest), según `PLATAFORMA`. Se prueba el
mismo binario que se libera —también si la app es Flutter (§3.2)—: nada de
builds de depuración con extensiones compiladas.

El aparato puede ser propio (`DISPOSITIVOS=local`, por omisión) o de Sauce
Labs (`DISPOSITIVOS=sauce`). Lo que cambia entre los dos vive acá y en
`config.py`; las pantallas y los casos no se enteran.
"""
from __future__ import annotations

import base64
import json
import urllib.error
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
    except urllib.error.HTTPError as e:
        # La granja puede contestar `/status` con un 4xx (pide credenciales, o
        # no lo publica): hay servidor, que es lo único que se pregunta. Con un
        # Appium propio sigue siendo caída, como siempre.
        if not (config.EN_SAUCE and e.code < 500):
            return (f"ambiente: Appium no responde en {config.APPIUM_URL} "
                    f"(HTTPError {e.code}). No se corrió nada contra un servidor caído")
    except Exception as e:  # red, conexión rechazada, respuesta que no es Appium
        return (f"ambiente: Appium no responde en {config.APPIUM_URL} "
                f"({type(e).__name__}). No se corrió nada contra un servidor caído")
    return ""


def abrir(nombre: str = ""):
    """La sesión de Appium. `nombre` es cómo se ve la sesión en Sauce (la
    corrida, o el caso si se abre una por caso); con un aparato local no se usa."""
    from appium import webdriver

    opciones = _opciones_ios() if config.ES_IOS else _opciones_android()
    if config.EN_SAUCE:
        opciones.load_capabilities(capacidades_sauce(nombre))
    driver = webdriver.Remote(config.APPIUM_URL, options=opciones)
    caps = driver.capabilities or {}
    modelo = caps.get("deviceModel") or caps.get("deviceName") or ""
    version = caps.get("platformVersion") or ""
    if modelo:
        DISPOSITIVO["descripcion"] = (
            f"{modelo} / {'iOS' if config.ES_IOS else 'Android'} {version}".strip())
        if config.EN_SAUCE:
            # Al manifiesto: el mismo modelo en la granja y en la mesa no es el
            # mismo aparato, y un rojo que sólo pasa en uno de los dos se busca ahí.
            DISPOSITIVO["descripcion"] += " · Sauce Labs"
    if config.EN_SAUCE:
        # Para marcar el resultado por la API al final (`marcar_por_api`).
        DISPOSITIVO["sesion_sauce"] = driver.session_id
    return driver


def capacidades_sauce(nombre: str = "") -> dict:
    """Lo que se agrega a las capacidades de la plantilla para Sauce Labs.

    Orden de la mezcla, de menos a más fuerte: la plantilla, después
    `APPIUM_CAPACIDADES` (qué emulador, qué versión: lo elige quien arma), y
    al final lo que no se negocia —las credenciales y los tiempos—. Con un
    préstamo de QORA (`APPIUM_DE_QORA`) no van credenciales: las pone QORA. Un
    `sauce:options` que venga en `APPIUM_CAPACIDADES` se conserva y se completa,
    no se pisa entero.

    Función pura, sin Appium: la prueba `tests_unit/test_dispositivos.py` la
    mira sin abrir nada.
    """
    extra = config.capacidades_extra()
    sauce = dict(extra.get("sauce:options") or {})
    if config.APPIUM_DE_QORA:
        # Ni las que trajera el JSON: QORA las borra igual, y no tienen por qué viajar.
        sauce.pop("username", None)
        sauce.pop("accessKey", None)
    else:
        sauce.update(username=config.SAUCE_USERNAME, accessKey=config.SAUCE_ACCESS_KEY)
    if nombre:
        sauce.setdefault("name", nombre)
    if config.SAUCE_BUILD:
        sauce.setdefault("build", config.SAUCE_BUILD)
    # Sin túnel, el aparato sale a internet desde Sauce y no llega al backend
    # que está detrás de la VPN del cliente: la app se queda sin red.
    if config.SAUCE_TUNEL:
        sauce.setdefault("tunnelName", config.SAUCE_TUNEL)
        if config.SAUCE_TUNEL_DUENO:
            sauce.setdefault("tunnelOwner", config.SAUCE_TUNEL_DUENO)
    # Claude Code piensa entre un comando y el siguiente, a veces más de un
    # minuto (MIGRACION.md §4.4): con el corte por omisión de la granja (90 s)
    # la sesión moría mientras se armaba un caso. 300 s en los dos lados.
    sauce["idleTimeout"] = 300
    return {**extra, "appium:newCommandTimeout": 300, "sauce:options": sauce}


def enlace_sesion(driver) -> str:
    """Dónde ver esta sesión en Sauce (video, registro de Appium), o vacío.

    Sauce graba su propio video: en vez de grabar uno acá, el reporte lleva
    el enlace. La región por omisión (`us-west-1`) vive en `app.saucelabs.com`;
    las demás llevan la región en el nombre.
    """
    if not config.EN_SAUCE:
        return ""
    sesion = getattr(driver, "session_id", "") or ""
    if not sesion:
        return ""
    sitio = ("app.saucelabs.com" if config.SAUCE_REGION == "us-west-1"
             else f"app.{config.SAUCE_REGION}.saucelabs.com")
    return f"https://{sitio}/tests/{sesion}"


def marcar_resultado(driver, paso: bool) -> None:
    """Le dice a Sauce si la sesión pasó: sin esto la granja muestra todas como
    «completas» y su pantalla no sirve para encontrar el rojo. Nunca lanza: es
    un extra, y una sesión que ya murió no puede tapar el resultado real."""
    if not config.EN_SAUCE:
        return
    try:
        driver.execute_script(f"sauce:job-result={'passed' if paso else 'failed'}")
    except Exception:
        pass


def marcar_por_api(paso: bool, _abrir=None) -> bool:
    """El resultado de la sesión en Sauce, por su API y no por el driver.

    `sauce:job-result` por el driver no alcanzó: el 2026-11-16 una corrida iOS
    con un caso roto quedó «pasada» en Sauce (la Android, en cambio, quedó
    bien). Por la API no depende de en qué estado quedó la sesión, y se llama
    al final de la corrida (`pytest_sessionfinish`), con el recuento ya
    cerrado. Nunca lanza: es un extra; el resultado de verdad es el de pytest.
    Devuelve si Sauce lo aceptó.

    Con un préstamo de QORA (`APPIUM_DE_QORA`) no se marca: la cuenta es de
    QORA y la suite no la tiene. Queda el `sauce:job-result` por el driver
    (`marcar_resultado`), que pasa por el reenvío sin cuenta. Marcarlo por la
    API le tocaría a QORA al devolver, y hoy no lo hace: el contrato no le dice
    cómo terminó la corrida."""
    sesion = DISPOSITIVO.get("sesion_sauce")
    if config.APPIUM_DE_QORA:
        return False
    if not (config.EN_SAUCE and sesion and config.SAUCE_USERNAME and config.SAUCE_ACCESS_KEY):
        return False
    url = (f"https://api.{config.SAUCE_REGION}.saucelabs.com/rest/v1/"
           f"{config.SAUCE_USERNAME}/jobs/{sesion}")
    credencial = base64.b64encode(
        f"{config.SAUCE_USERNAME}:{config.SAUCE_ACCESS_KEY}".encode()).decode()
    pedido = urllib.request.Request(
        url, method="PUT", data=json.dumps({"passed": bool(paso)}).encode(),
        headers={"Authorization": f"Basic {credencial}", "Content-Type": "application/json"})
    try:
        with (_abrir or urllib.request.urlopen)(pedido, timeout=20) as r:
            return 200 <= r.status < 300
    except Exception as e:  # sin la llave en el mensaje: sólo el tipo y el código
        print(f"[sauce] no se pudo marcar el resultado: {type(e).__name__} {getattr(e, 'code', '')}".rstrip())
        return False


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
    # En la granja el aparato lo eligen las capacidades; un UDID de la mesa
    # local que quedó en el `.env` pediría uno que allá no existe.
    if config.ANDROID_UDID and not config.EN_SAUCE:
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
    if config.IOS_UDID and not config.EN_SAUCE:
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
            self._aceptar_permisos_del_sistema()
            return True
        self._driver.execute_script("mobile: clearApp", {"appId": config.PAQUETE})
        self._driver.execute_script("mobile: changePermissions", {
            "permissions": "all", "appPackage": config.PAQUETE, "action": "grant"})
        self._driver.activate_app(config.PAQUETE)
        return True

    # Los botones de los avisos de permiso de iOS (notificaciones, ubicación,
    # rastreo), en inglés y en español. Sólo éstos: un aviso PROPIO de la app
    # con otros botones no se toca, porque puede ser justo lo que el caso prueba.
    # Por eso no se usa `autoAcceptAlerts`, que aceptaría cualquiera.
    BOTONES_DE_PERMISO = ("Allow", "Permitir", "Allow While Using App",
                          "Permitir al usarse la app", "Allow Once", "Permitir una vez")

    def _aceptar_permisos_del_sistema(self, segundos: float = 8.0) -> None:
        """Después de `clearApp`, iOS vuelve a pedir los permisos al abrir la app
        y el aviso tapa la pantalla (en Android, `changePermissions` los concede
        antes de abrir; en iOS no hay equivalente sin herramientas del Mac, y en
        la granja no las hay). Se espera unos segundos a que aparezca y se toca
        el botón de permitir; si no aparece ninguno, no pasa nada."""
        import time
        limite = time.monotonic() + segundos
        sin_aviso = 0
        while time.monotonic() < limite:
            try:
                botones = self._driver.execute_script("mobile: alert", {"action": "getButtons"}) or []
            except Exception:
                # Sin aviso abierto. Dos vistas seguidas sin aviso, pasado el
                # primer segundo, y ya no va a venir.
                sin_aviso += 1
                if sin_aviso >= 4:
                    return
                time.sleep(0.75)
                continue
            sin_aviso = 0
            boton = next((b for b in botones if b in self.BOTONES_DE_PERMISO), None)
            if boton is None:
                return  # un aviso que no es de permisos: lo decide el caso
            try:
                self._driver.execute_script("mobile: alert", {"action": "accept", "buttonLabel": boton})
            except Exception:
                pass
            time.sleep(0.5)

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
