"""El aparato enchufado a esta máquina, para correr en local sin QORA.

Ningún aparato vive escrito en la suite: los teléfonos cambian, y el que usa
el CI se elige en la pantalla de QORA (que lo pasa como `ANDROID_UDID` o
`IOS_UDID` al prestarlo). En local, sin préstamo, se mira lo que hay:

- Android: `adb devices` (teléfonos y emuladores listos).
- iOS: `xcrun devicectl` (iPhones físicos conectados y emparejados) y
  `xcrun simctl` (simuladores encendidos).

Un físico gana a un emulador o simulador: si alguien enchufó un teléfono es
porque quiere correr ahí, y el simulador no tiene el build que se libera. Si
hay varios, o ninguno, se dice en UNA línea (cuál se tomó y cómo pedir otro):
sin esa línea el único indicio de que se corrió contra el aparato equivocado
sería un modelo raro en el manifiesto.

Nada de acá lanza: sin `adb` o sin Xcode se devuelve una lista vacía y quien
llama decide (en iOS, `faltantes()` sigue pidiendo `IOS_UDID`).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

#: `adb devices` y `simctl` son instantáneos; `devicectl` tarda unos segundos
#: la primera vez porque despierta su servicio.
TIMEOUT = 30


def _correr(cmd: list[str]) -> str:
    """La salida del comando, o vacío si no está o falla."""
    if not shutil.which(cmd[0]):
        return ""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout or ""


def android() -> list[tuple[str, bool]]:
    """`(serial, es_fisico)` de cada aparato listo, en el orden de `adb`.

    Los `offline` y `unauthorized` no cuentan: aparecen en la lista pero no
    aceptan una sesión, y elegirlos cambiaría «no hay aparato» por un error
    más críptico después."""
    encontrados = []
    for linea in _correr(["adb", "devices"]).splitlines()[1:]:
        partes = linea.split()
        if len(partes) >= 2 and partes[1] == "device":
            encontrados.append((partes[0], not partes[0].startswith("emulator-")))
    return encontrados


def ios() -> list[tuple[str, bool]]:
    """`(udid, es_fisico)`: primero los iPhones conectados, después los simuladores encendidos."""
    encontrados = []
    # `devicectl` sólo escribe JSON a un archivo: por eso el temporal.
    with tempfile.TemporaryDirectory() as carpeta:
        destino = os.path.join(carpeta, "aparatos.json")
        _correr(["xcrun", "devicectl", "list", "devices", "--quiet", "--json-output", destino])
        try:
            with open(destino, encoding="utf-8") as f:
                datos = json.load(f)
        except (OSError, ValueError):
            datos = {}
    for aparato in (datos.get("result") or {}).get("devices") or []:
        hw = aparato.get("hardwareProperties") or {}
        conexion = aparato.get("connectionProperties") or {}
        # Emparejado y con un transporte (cable o red): uno que sólo se
        # recuerda de otra vez aparece igual, pero sin transporte.
        if (hw.get("platform") == "iOS" and hw.get("reality") == "physical"
                and hw.get("udid") and conexion.get("transportType")
                and conexion.get("pairingState") == "paired"):
            encontrados.append((hw["udid"], True))
    try:
        sims = json.loads(_correr(["xcrun", "simctl", "list", "devices", "booted", "-j"]) or "{}")
    except ValueError:
        sims = {}
    for lista in (sims.get("devices") or {}).values():
        for sim in lista:
            if sim.get("state") == "Booted" and sim.get("udid"):
                encontrados.append((sim["udid"], False))
    return encontrados


def elegir(lista: list[tuple[str, bool]]) -> tuple[str, str]:
    """`(udid, línea)`: el aparato a usar y, si no fue obvio, por qué ése.

    La línea va vacía con uno solo; con varios nombra el elegido y los demás;
    con ninguno lo dice. Siempre una sola línea."""
    if not lista:
        return "", "No hay ningún aparato conectado ni encendido en esta máquina."
    fisicos = [u for u, fisico in lista if fisico]
    elegido = fisicos[0] if fisicos else lista[0][0]
    if len(lista) == 1:
        return elegido, ""
    otros = ", ".join(u for u, _ in lista if u != elegido)
    return elegido, (f"Hay {len(lista)} aparatos: se usa {elegido} (quedan {otros}); "
                     "para otro, ANDROID_UDID o IOS_UDID en el .env.")


def detectar(es_ios: bool) -> str:
    """El udid del aparato de esta máquina, o vacío; la línea, si hace falta, sale ya.

    A `sys.__stderr__` y no a `print`: pytest captura la salida de cada caso,
    y un aviso que sólo se ve si el caso falla llega tarde."""
    udid, linea = elegir(ios() if es_ios else android())
    if linea:
        print(f"[aparato] {linea}", file=sys.__stderr__ or sys.stderr, flush=True)
    return udid
