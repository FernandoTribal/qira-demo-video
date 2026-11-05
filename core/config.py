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
    archivo = Path(ruta) if Path(ruta).is_absolute() else RAIZ / ruta
    return str(archivo) if archivo.is_file() else ""


PAQUETE = _v(f"{PREFIJO}_PAQUETE")
ACTIVIDAD = _v(f"{PREFIJO}_ACTIVIDAD")
APK = _binario(f"{PREFIJO}_APK")
BUNDLE_ID = _v(f"{PREFIJO}_BUNDLE_ID")
IPA = _binario(f"{PREFIJO}_IPA")

# ── El dispositivo ─────────────────────────────────────────────────────────
APPIUM_URL = _v("APPIUM_URL", "http://127.0.0.1:4723").rstrip("/")
ANDROID_UDID = _v("ANDROID_UDID")
# En iOS el UDID no es opcional en la práctica: sin él XCUITest se va a un
# SIMULADOR, que no tiene el build que se libera. Lo exige `faltantes()`.
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


def udid() -> str:
    return IOS_UDID if ES_IOS else ANDROID_UDID


# ── Lo que se exige, y cuándo ──────────────────────────────────────────────

def faltantes() -> list[str]:
    """Las variables sin las que no se puede abrir la app en esta plataforma.

    Una función y no una comprobación al importar: la llama la guarda de
    ambiente justo antes del primer caso que necesita el dispositivo.
    """
    if PLATAFORMA not in PLATAFORMAS:
        return [f"PLATAFORMA (vale {PLATAFORMA!r}; hay: {', '.join(PLATAFORMAS)})"]
    if ES_IOS:
        pedidas = {f"{PREFIJO}_BUNDLE_ID": BUNDLE_ID, "IOS_UDID": IOS_UDID}
    else:
        pedidas = {f"{PREFIJO}_PAQUETE": PAQUETE, f"{PREFIJO}_ACTIVIDAD": ACTIVIDAD}
    return [nombre for nombre, valor in pedidas.items() if not valor]


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
