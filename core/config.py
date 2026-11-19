"""Lo que la suite sabe del ambiente de App móvil · Demo. Se lee; no se inventa.

El orden de lectura, de menos a más fuerte:

    .env                  lo común a todos los ambientes
    .env.<AMBIENTE>       lo propio de ese ambiente, y pisa a `.env`
    el entorno real       pisa a los dos

Que el entorno real gane no es un detalle: es lo que deja que el CI ponga
`PLATAFORMA` o `PROPOSITO` sin reescribir archivos, y que
`AMBIENTE=qa ./run.sh humo` haga lo que dice.

**Nada se exige al importar.** Una credencial que falta no revienta nada acá:
revienta —con un mensaje que nombra la variable— cuando alguien la pide. Si se
exigiera al importar, `./run.sh --unitarias` necesitaría credenciales y un
teléfono para comprobar que un docstring tiene su ID, y la etapa barata del CI
dejaría de ser barata.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import dotenv_values

RAIZ = Path(__file__).resolve().parent.parent
PREFIJO = "APP"


class ErrorDeConfiguracion(RuntimeError):
    """Falta algo que sólo quien opera el ambiente puede poner."""


def _cargar() -> None:
    reales = set(os.environ)
    base = dotenv_values(RAIZ / ".env")
    ambiente = (os.environ.get("AMBIENTE") or base.get("AMBIENTE") or "").strip()
    propio = dotenv_values(RAIZ / f".env.{ambiente}") if ambiente else {}
    for clave, valor in {**base, **propio}.items():
        if clave not in reales and valor is not None:
            os.environ[clave] = valor


_cargar()


def _v(nombre: str, defecto: str = "") -> str:
    return (os.environ.get(nombre) or defecto).strip()


# ── El ambiente y la plataforma ────────────────────────────────────────────
AMBIENTE = _v("AMBIENTE", "sin declarar")
# Una sola suite para las dos plataformas: el caso se escribe una vez y la
# diferencia vive en `core/`. Si fuera `android` por error estando en un iPhone,
# la corrida no fallaría: mediría otro aparato y lo entregaría como bueno. Por
# eso lo decide `run.sh` y se exporta, y por eso un valor raro no se corrige.
PLATAFORMA = _v("PLATAFORMA", "android").lower()
ES_IOS = PLATAFORMA == "ios"
PLATAFORMAS = ("android", "ios")

# ── La app ─────────────────────────────────────────────────────────────────
def _binario(nombre: str) -> str:
    """El APK o el IPA a instalar al abrir la sesión, o vacío.

    Relativo a la suite (`apk/app-1.2.3.apk`), que es como lo escribe QIRA: una
    ruta absoluta es de una máquina, y el CI clona en otra. Y si el archivo no
    está, vacío: el binario no se versiona, así que un clon limpio no lo tiene
    y ahí la app ya está instalada en el dispositivo. Pasarle a Appium una ruta
    que no existe rompería la sesión antes del primer caso.
    """
    ruta = _v(nombre)
    if not ruta:
        return ""
    # Lo que no es un archivo de esta máquina va tal cual: `storage:<id>` es la
    # app ya subida a Sauce Storage, y una URL la descarga quien abre la sesión.
    # Las dos son la única forma de darle la app a un Appium que no comparte
    # disco con la suite (una granja, o el Mac visto desde el servidor), y
    # tratarlas como ruta las convertía en «no está» y la sesión abría sin app.
    if ruta.startswith(("storage:", "http://", "https://")):
        return ruta
    archivo = Path(ruta) if Path(ruta).is_absolute() else RAIZ / ruta
    return str(archivo) if archivo.is_file() else ""


def binario_declarado() -> tuple:
    """(variable, valor tal cual está escrito) del binario de esta plataforma.

    Para quien tiene que SUBIR la app antes de abrir la sesión (la receta, con
    Sauce): `_binario()` ya descartó lo que no existe, y acá hace falta saber
    qué se pidió aunque no exista, para decirlo con su nombre.
    """
    nombre = f"{PREFIJO}_{'IPA' if ES_IOS else 'APK'}"
    return nombre, _v(nombre)


PAQUETE = _v(f"{PREFIJO}_PAQUETE")
ACTIVIDAD = _v(f"{PREFIJO}_ACTIVIDAD")
APK = _binario(f"{PREFIJO}_APK")
BUNDLE_ID = _v(f"{PREFIJO}_BUNDLE_ID")
IPA = _binario(f"{PREFIJO}_IPA")

# ── El dispositivo ─────────────────────────────────────────────────────────
# Dónde está el aparato: `local` (el emulador, el simulador o el teléfono que
# ve el Appium de `APPIUM_URL`) o `sauce` (un emulador o simulador de Sauce
# Labs). Es el contrato que QIRA usa al armar y la receta al correr: los
# nombres de abajo no se cambian sin cambiar los dos.
DISPOSITIVOS = _v("DISPOSITIVOS", "local").lower()
MODOS_DE_DISPOSITIVOS = ("local", "sauce")
EN_SAUCE = DISPOSITIVOS == "sauce"

# `us-west-1`, `eu-central-1`… Decide a qué Appium se le habla y dónde se ve
# la sesión después.
SAUCE_REGION = _v("SAUCE_REGION", "us-west-1").lower()
SAUCE_USERNAME = _v("SAUCE_USERNAME")
SAUCE_ACCESS_KEY = _v("SAUCE_ACCESS_KEY")  # secreto: en CI lo pone la credencial `sauce-labs`
# Agrupa las sesiones de una corrida en la pantalla de Sauce. Lo pone el CI.
SAUCE_BUILD = _v("SAUCE_BUILD")
# El túnel de Sauce Connect por el que sale el aparato de la granja, para las
# apps cuyo backend sólo se alcanza por una VPN (OPERACION_QE.md §8). Va por
# ambiente: el `.env.uat` de un banco lo nombra; el de un sitio público, no.
# No se llaman SAUCE_TUNNEL_NAME a propósito: ése lo lee el propio `sc`.
SAUCE_TUNEL = _v("SAUCE_TUNEL")
# Quién abrió el túnel, si no es la misma cuenta que corre (túnel compartido).
SAUCE_TUNEL_DUENO = _v("SAUCE_TUNEL_DUENO")

_APPIUM_SAUCE = f"https://ondemand.{SAUCE_REGION}.saucelabs.com:443/wd/hub"
APPIUM_URL = _v("APPIUM_URL", _APPIUM_SAUCE if EN_SAUCE else "http://127.0.0.1:4723").rstrip("/")
# `1` cuando `APPIUM_URL` es la dirección de un préstamo de QORA
# (`<QORA>/wd/<token>`, CONTRATO_APARATOS.md): QORA reenvía al Appium de una
# estación o al hub de Sauce y, en Sauce, pone la cuenta él (borra la que mande
# la suite). Entonces la suite no pide `SAUCE_USERNAME`/`SAUCE_ACCESS_KEY` ni
# marca el resultado por la API de Sauce, que sí la necesita. La pone QIRA al
# armar con un préstamo. Es una variable y no se adivina por la dirección: el
# hub de Sauce también termina en `/wd/hub`.
APPIUM_DE_QORA = _v("APPIUM_DE_QORA").lower() in ("1", "si", "sí", "true")
# Capacidades NO secretas que se mezclan con las de la plantilla, en JSON:
#   {"appium:deviceName":"Android GoogleAPI Emulator","appium:platformVersion":"14.0"}
# Es lo que elige QUÉ emulador o simulador pedirle a la granja; con un aparato
# local suele ir vacío. Crudo acá y leído en `capacidades_extra()`: un JSON
# roto no puede romper el import (ver el docstring del módulo).
APPIUM_CAPACIDADES = _v("APPIUM_CAPACIDADES")

# El aparato concreto. NO se escribe en la suite ni en el `.env.ejemplo`: los
# teléfonos cambian, y el del CI se elige en la pantalla de QORA, que lo pone
# acá al prestarlo. En local, vacío es lo normal: `udid()` mira lo enchufado
# (`core/aparato_local.py`). Ponerlo en el `.env` sólo para fijar uno cuando
# hay varios.
ANDROID_UDID = _v("ANDROID_UDID")
# En iOS el UDID no es opcional en la práctica con un aparato propio: sin él
# XCUITest se va a un SIMULADOR, que no tiene el build que se libera. Si no se
# detecta ninguno, lo exige `faltantes()`. En Sauce no hay UDID que dar: el
# simulador lo elige la granja por las capacidades.
IOS_UDID = _v("IOS_UDID")

# Lo que se probó. Lo pone el CI; a mano queda «sin declarar», que se reclama.
BUILD = _v("BUILD", "sin declarar")

# ── La evidencia de un caso que falla (core/evidencia.py) ──────────────────
# La captura y el árbol de la pantalla se adjuntan siempre que un caso falla:
# son baratos. El video no: grabar cuesta en cada caso, verde o rojo.
#   fallos   se graba cada caso y se adjunta sólo si falló (por omisión)
#   siempre  se adjunta también en los verdes (para mostrar un flujo)
#   nunca    no se graba: ni se adjunta ni se paga
EVIDENCIA_VIDEO = _v("EVIDENCIA_VIDEO", "fallos").lower()
MODOS_DE_VIDEO = ("fallos", "siempre", "nunca")


_DETECTADO: dict = {}


def udid() -> str:
    """El aparato al que se le abre la sesión, o vacío.

    El de la variable si está (lo pone QORA al prestar, o quien fija uno a
    mano); si no, el que esté enchufado a ESTA máquina. Sólo se detecta con el
    Appium de esta máquina: con uno de QORA o de otra, lo que vea `adb` acá no
    es lo que tiene ese Appium. En Sauce, nunca: el aparato lo eligen las
    capacidades. Se detecta una vez por corrida (la línea de aviso, también)."""
    if EN_SAUCE:
        return ""
    fijo = IOS_UDID if ES_IOS else ANDROID_UDID
    if fijo or APPIUM_DE_QORA or not _appium_de_esta_maquina():
        return fijo
    if ES_IOS not in _DETECTADO:
        from core import aparato_local

        _DETECTADO[ES_IOS] = aparato_local.detectar(ES_IOS)
    return _DETECTADO[ES_IOS]


def _appium_de_esta_maquina() -> bool:
    from urllib.parse import urlparse

    return (urlparse(APPIUM_URL).hostname or "") in ("127.0.0.1", "localhost", "::1")


def capacidades_extra() -> dict:
    """`APPIUM_CAPACIDADES` leído, o `{}` si no hay.

    Lanza `ErrorDeConfiguracion` si no es un objeto JSON: una capacidad mal
    escrita que se ignorara en silencio abriría la sesión en OTRO aparato (el
    que la granja dé por omisión), y la corrida se entregaría como si fuera el
    pedido.
    """
    valor = {}
    if APPIUM_CAPACIDADES:
        try:
            valor = json.loads(APPIUM_CAPACIDADES)
        except ValueError as e:
            raise ErrorDeConfiguracion(f"APPIUM_CAPACIDADES no es JSON válido ({e})") from None
        if not isinstance(valor, dict):
            raise ErrorDeConfiguracion("APPIUM_CAPACIDADES tiene que ser un objeto JSON {…}")
    # En la granja, sin dispositivo ni versión Sauce no abre la sesión. QIRA
    # los manda al armar (los del panel); una corrida de QORA no los trae, y
    # se piden los mismos genéricos que QIRA usa por omisión.
    if EN_SAUCE:
        valor.setdefault("appium:deviceName", "iPhone Simulator" if ES_IOS else "Android GoogleAPI Emulator")
        valor.setdefault("appium:platformVersion", "18.0" if ES_IOS else "14.0")
    return valor


# ── Lo que se exige, y cuándo ──────────────────────────────────────────────

def faltantes() -> list[str]:
    """Las variables sin las que no se puede abrir la app en esta plataforma.

    Una función y no una comprobación al importar: la llama la guarda de
    ambiente justo antes del primer caso que necesita el dispositivo.
    """
    if PLATAFORMA not in PLATAFORMAS:
        return [f"PLATAFORMA (vale {PLATAFORMA!r}; hay: {', '.join(PLATAFORMAS)})"]
    if DISPOSITIVOS not in MODOS_DE_DISPOSITIVOS:
        return [f"DISPOSITIVOS (vale {DISPOSITIVOS!r}; hay: {', '.join(MODOS_DE_DISPOSITIVOS)})"]
    if ES_IOS:
        pedidas = {f"{PREFIJO}_BUNDLE_ID": BUNDLE_ID}
        if not EN_SAUCE:
            # El de la variable o el detectado: sólo falta si no hay ninguno.
            pedidas["IOS_UDID"] = udid()
    else:
        pedidas = {f"{PREFIJO}_PAQUETE": PAQUETE, f"{PREFIJO}_ACTIVIDAD": ACTIVIDAD}
    if EN_SAUCE:
        # El emulador de la granja nace vacío en cada sesión: sin la app no
        # hay nada que abrir, y el primer caso fallaría como un defecto.
        variable, _ = binario_declarado()
        pedidas[variable] = IPA if ES_IOS else APK
        if not APPIUM_DE_QORA:
            pedidas.update({"SAUCE_USERNAME": SAUCE_USERNAME, "SAUCE_ACCESS_KEY": SAUCE_ACCESS_KEY})
    if APPIUM_DE_QORA:
        # Sin la dirección del préstamo, el valor por omisión sería el hub de
        # Sauce (o el Appium de esta máquina), y sin cuenta ahí no se entra.
        pedidas["APPIUM_URL"] = _v("APPIUM_URL")
    faltan = [nombre for nombre, valor in pedidas.items() if not valor]
    try:
        capacidades_extra()
    except ErrorDeConfiguracion as e:
        faltan.append(str(e))
    return faltan


def url(clave: str = "principal") -> str:
    """La URL de un sistema que la suite también toca (backoffice, API…).

    `principal` es `APP_URL`; cualquier otra es `APP_<CLAVE>_URL`.
    """
    nombre = _nombre_url(clave)
    valor = _v(nombre)
    if not valor:
        raise ErrorDeConfiguracion(
            f"falta {nombre} en el .env: no sé dónde está «{clave}» en el "
            f"ambiente {AMBIENTE}")
    return valor.rstrip("/")


def url_declarada(clave: str = "principal") -> bool:
    return bool(_v(_nombre_url(clave)))


def credencial(rol: str) -> tuple[str, str]:
    """(usuario, clave) de un rol. Sin valores por omisión, a propósito.

    Una cuenta inventada «para que corra» es el peor caso posible: entra con
    otra identidad y el caso pasa en verde sobre datos que nadie va a revisar.
    """
    base = f"{PREFIJO}_{rol.strip().upper()}"
    usuario, clave = _v(f"{base}_USUARIO"), _v(f"{base}_CLAVE")
    faltan = [n for n, v in ((f"{base}_USUARIO", usuario),
                             (f"{base}_CLAVE", clave)) if not v]
    if faltan:
        raise ErrorDeConfiguracion(
            f"faltan las credenciales del rol «{rol}»: {', '.join(faltan)} "
            f"(van en .env o .env.{AMBIENTE}, nunca en el código)")
    return usuario, clave


def _nombre_url(clave: str) -> str:
    clave = clave.strip().upper()
    return f"{PREFIJO}_URL" if clave in ("", "PRINCIPAL") else f"{PREFIJO}_{clave}_URL"
