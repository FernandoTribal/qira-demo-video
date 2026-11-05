"""La primera pantalla que muestra la app al abrir.

`ANCLAS` arranca vacía a propósito: los textos que la identifican se sacan del
árbol REAL de la app, no se adivinan (principio 1). Mientras esté vacía, «está
cargada» significa sólo «la app está en primer plano y pintó algo», que es lo
que el caso de humo necesita para decidir si vale la pena correr los demás.
Llenarla es el primer pendiente de `docs/PENDIENTE.md`.
"""
from __future__ import annotations

from core.pantalla import Screen


class PantallaInicio(Screen):
    NAME = "Inicio"
    ANCLAS: tuple = ()

    def is_loaded(self) -> bool:
        if not self._sesion.en_primer_plano():
            return False
        arbol = self.arbol()
        return bool(arbol.nodos) and self.en_el_arbol(arbol)
