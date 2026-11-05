"""Pantalla de bienvenida y el diálogo de notificaciones que la tapa en iOS."""
from __future__ import annotations

from core.pantalla import Screen


class DialogoNotificaciones(Screen):
    NAME = "Permiso de notificaciones"
    ANCLAS: tuple = ("quiere enviarte notificaciones",)

    def permitir(self) -> None:
        self.tocar("Permitir", exacto=True)


class Bienvenida(Screen):
    NAME = "Bienvenida"
    ANCLAS: tuple = ("Saltar tutorial",)

    def saltar_tutorial(self) -> None:
        self.tocar("Saltar tutorial", exacto=True)
