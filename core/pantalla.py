"""Leer la interfaz por snapshot y esperar por predicado (§5.1, §5.2).

Se lee el árbol COMPLETO una vez y se filtra en Python. Un `find_element` por
consulta paga el viaje al dispositivo muchas veces y falla distinto según el
timing; leer el árbol es tan barato que se puede volver a leer hasta que se
cumpla lo que se espera.

**Ninguna espera es por reloj.** `esperar()` vuelve a leer hasta que el
predicado se cumple o se llega al tope. No hay intervalo de muestreo: el viaje
de ida y vuelta al dispositivo ya es el ritmo, y no se paga nunca el peor caso.
"""
from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Callable, Iterator, Optional

# Un TECHO, no una expectativa: se llega sólo cuando algo va mal.
TOPE = 20.0

_CAJA = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")
_TOCABLES_IOS = ("Button", "Cell", "Link", "TextField", "SearchField", "Switch", "Image")


class Espera(TimeoutError):
    """Se agotó el tope. El mensaje nombra lo que se esperaba."""


@dataclass(frozen=True)
class Nodo:
    texto: str
    desc: str
    ident: str
    clase: str
    tocable: bool
    visible: bool
    caja: tuple

    @property
    def centro(self) -> tuple:
        x1, y1, x2, y2 = self.caja
        return (x1 + x2) // 2, (y1 + y2) // 2


class Arbol:
    def __init__(self, xml: str) -> None:
        self.nodos = list(_parsear(xml))

    def buscar(self, contiene: str = "", *, ident: str = "", exacto: bool = False) -> list:
        """Por texto visible, descripción de accesibilidad o identificador.

        El identificador estable es lo que conviene pedirle al equipo de
        producto el día uno (§3.2): anclar por texto se rompe con una tilde.

        `exacto` para TOCAR un botón por su rótulo: «Allow» contenido encuentra
        primero el mensaje «Allow App … to send you notifications?» y el toque
        cae en el texto, no en el botón (medido el 2026-10-26).
        """
        c = contiene.casefold()
        if exacto:
            coincide = lambda n: c in (n.texto.casefold(), n.desc.casefold())
        else:
            coincide = lambda n: c in n.texto.casefold() or c in n.desc.casefold()
        return [n for n in self.nodos
                if (not ident or n.ident == ident) and (not c or coincide(n))]

    def uno(self, contiene: str = "", **kw) -> Optional[Nodo]:
        encontrados = self.buscar(contiene, **kw)
        return encontrados[0] if encontrados else None

    def hay(self, contiene: str = "", **kw) -> bool:
        return bool(self.buscar(contiene, **kw))


class Screen:
    """Una pantalla. El contrato con `v` son `NAME` e `is_loaded()`."""

    NAME = "sin nombre"
    # Lo que identifica la pantalla. Todas tienen que estar.
    ANCLAS: tuple = ()

    def __init__(self, sesion) -> None:
        self._sesion = sesion

    def arbol(self) -> Arbol:
        return Arbol(self._sesion.fuente())

    def en_el_arbol(self, arbol: Arbol) -> bool:
        return all(arbol.hay(a) for a in self.ANCLAS)

    def is_loaded(self) -> bool:
        return self.en_el_arbol(self.arbol())

    def esperar(self, hasta: Callable[[Arbol], bool], *, que: str,
                tope: float = TOPE) -> Arbol:
        """`que` nombra lo que se espera: «que algo cargue» no es un predicado,
        es una carrera que se gana casi siempre (§5.2)."""
        limite = time.monotonic() + tope
        while True:
            arbol = self.arbol()
            if hasta(arbol):
                return arbol
            if time.monotonic() >= limite:
                raise Espera(f"se agotaron {tope:.0f} s esperando {que} en «{self.NAME}»")

    def aparece(self, *, tope: float = TOPE) -> bool:
        """¿Llega a estar cargada dentro del tope? Devuelve un HECHO; no lanza.

        `esperar()` lanza, y una excepción de espera se lee como problema de
        ambiente: correcto cuando el caso NECESITA algo para seguir, incorrecto
        cuando está preguntando. Lo que el caso afirma lo afirma con `v`.
        """
        limite = time.monotonic() + tope
        while True:
            if self.is_loaded():
                return True
            if time.monotonic() >= limite:
                return False

    def tocar(self, contiene: str = "", **kw) -> None:
        nodo = self.arbol().uno(contiene, **kw)
        if nodo is None:
            raise LookupError(f"no está «{contiene or kw}» en «{self.NAME}»")
        self._sesion.tocar(*nodo.centro)


def _parsear(xml: str) -> Iterator[Nodo]:
    """Reparte por lo que dice el ÁRBOL, no la configuración: un árbol mal
    leído por una variable equivocada da cero nodos y un rojo que culpa a la app."""
    try:
        raiz = ET.fromstring(xml)
    except ET.ParseError:
        return
    for el in raiz.iter():
        a = el.attrib
        tipo = a.get("type") or el.tag
        if tipo.startswith("XCUIElementType"):
            texto = a.get("label") or a.get("value") or ""
            nombre = a.get("name") or ""
            x, y = int(a.get("x", 0) or 0), int(a.get("y", 0) or 0)
            w, h = int(a.get("width", 0) or 0), int(a.get("height", 0) or 0)
            # En iOS `name` cae al `label` si nadie puso identificador: sólo
            # cuenta como identificador cuando difiere del texto visible.
            # iOS no publica `clickable`: se DERIVA del tipo, declarado como tal.
            yield Nodo(texto, nombre, nombre if nombre != texto else "", tipo,
                       tipo.endswith(_TOCABLES_IOS), a.get("visible") != "false",
                       (x, y, x + w, y + h))
        elif "bounds" in a:
            m = _CAJA.match(a["bounds"])
            caja = tuple(int(g) for g in m.groups()) if m else (0, 0, 0, 0)
            yield Nodo(a.get("text", ""), a.get("content-desc", ""),
                       a.get("resource-id", ""), a.get("class", ""),
                       a.get("clickable") == "true", a.get("displayed", "true") != "false",
                       caja)
