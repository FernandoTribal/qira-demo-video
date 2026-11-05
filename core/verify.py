"""El objeto `v`: aserciones suaves con diagnóstico (§5.3, Anexo A.11).

Un caso que valida doce cosas con `assert` se detiene en la primera; contra un
teléfono, cada vuelta de «corregir y volver a correr» cuesta un minuto. Este
objeto ACUMULA y falla una sola vez al final, con cada fallo numerado, su
esperado, su obtenido y una captura tomada en el momento.

Su contrato con lo que recibe son dos miembros: `.NAME` y `.is_loaded()`. Nada
del driver. Por esa puerta entra mañana una página web o un cliente de API sin
tocar una línea de acá.

Lo que NO hace: no espera (eso es de `core/pantalla.py`) y no da veredicto de
la corrida (cuenta y falla su propio caso).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

try:  # §7: el reporte es opcional; la suite corre igual sin él
    import allure
    from allure_commons.types import AttachmentType
except ImportError:  # pragma: no cover
    allure = None

# Literal, con los dos puntos y el espacio (§6.8). Se pone ACÁ y en ningún otro
# lado: así marcar los pasos no cuesta tocar cada caso, y no se puede olvidar.
PASO = "paso: "


class FalloCritico(AssertionError):
    """Lo único que corta un caso antes de `volcar()`."""


class FallosAcumulados(AssertionError):
    """Lo que lanza `volcar()`. Una clase propia para que la evidencia del
    cierre (`core/evidencia.py`) la reconozca: cada fallo ya adjuntó su
    captura en el momento, y otra tomada al final mostraría otra pantalla."""


@dataclass
class Fallo:
    que: str
    esperado: str
    obtenido: str

    def __str__(self) -> str:
        return f"{self.que}\n    esperado: {self.esperado}\n    obtenido: {self.obtenido}"


@dataclass
class Verify:
    capturar: Callable[[str], Optional[bytes]] = lambda _que: None
    fallos: list = field(default_factory=list)
    ok: int = 0
    # Un crítico ya hizo fallar el caso con el resumen completo. Si `volcar()`
    # lo lanzara otra vez, pytest contaría el mismo fallo dos veces: FAILED en
    # el caso y ERROR en el cierre de la fixture (visto el 2026-10-26).
    cortado: bool = False

    # ── Las verificaciones: todas abren un paso, acumulan y devuelven bool ──

    def que(self, condicion: Any, que: str, *, esperado: str = "se cumple",
            obtenido: str = "no se cumple") -> bool:
        return self._registrar(bool(condicion), que, esperado, obtenido)

    def igual(self, obtenido: Any, esperado: Any, que: str) -> bool:
        return self.que(obtenido == esperado, que,
                        esperado=repr(esperado), obtenido=repr(obtenido))

    def visible(self, nodo: Any, que: str) -> bool:
        esta = nodo is not None and getattr(nodo, "visible", True)
        return self.que(esta, que, esperado="visible",
                        obtenido="visible" if esta else "no está en pantalla")

    def texto(self, nodo: Any, esperado: str, que: str) -> bool:
        obtenido = getattr(nodo, "texto", None) if nodo is not None else None
        return self.que(obtenido == esperado, que,
                        esperado=repr(esperado), obtenido=repr(obtenido))

    def cargada(self, pantalla: Any) -> bool:
        """Crítica a propósito: si la pantalla no es la que el caso cree, todo
        lo que siga mide sobre otra cosa, y así se fabrican falsos verdes."""
        nombre = getattr(pantalla, "NAME", pantalla.__class__.__name__)
        return self.critical(pantalla.is_loaded(), f"la pantalla «{nombre}» está cargada",
                             esperado=f"«{nombre}» en pantalla",
                             obtenido="no se reconoció")

    def critical(self, condicion: Any, que: str, *, esperado: str = "se cumple",
                 obtenido: str = "no se cumple") -> bool:
        """Corta lo que invalida a las demás; ante la duda, se acumula."""
        if not self.que(condicion, que, esperado=esperado, obtenido=obtenido):
            self.cortado = True
            raise FalloCritico(self._resumen())
        return True

    # ── El cierre: lo llama la fixture, nunca el caso ─────────────────────

    def volcar(self) -> None:
        """Si lo llamara el caso, un `return` temprano dejaría verde un caso con
        fallos adentro: el falso verde fabricado por la herramienta anti-falsos
        verdes."""
        if not self.fallos:
            return
        resumen = self._resumen()
        if allure is not None:
            allure.attach(resumen, name="verificaciones",
                          attachment_type=AttachmentType.TEXT)
        if not self.cortado:
            raise FallosAcumulados(resumen)

    # ── Adentro ────────────────────────────────────────────────────────────

    def _registrar(self, ok: bool, que: str, esperado: str, obtenido: str) -> bool:
        if ok:
            self.ok += 1
        else:
            self.fallos.append(Fallo(que, esperado, obtenido))
        if allure is not None:
            with allure.step(f"{PASO}{que}"):
                if not ok:
                    allure.attach(f"esperado: {esperado}\nobtenido: {obtenido}",
                                  name="diagnóstico", attachment_type=AttachmentType.TEXT)
                    # En el momento del fallo: al volcar la pantalla ya es otra.
                    imagen = self.capturar(que)
                    if imagen:
                        allure.attach(imagen, name="captura",
                                      attachment_type=AttachmentType.PNG)
        return ok

    def _resumen(self) -> str:
        lineas = [f"{len(self.fallos)} verificaciones fallaron ({self.ok} pasaron):"]
        lineas += [f"{i}. {f}" for i, f in enumerate(self.fallos, 1)]
        return "\n".join(lineas)
