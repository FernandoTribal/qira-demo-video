"""Inicio con la sesión abierta (la pantalla a la que se llega tras el login)."""
from __future__ import annotations

from core.pantalla import Screen


class InicioConSesion(Screen):
    NAME = "Inicio con sesión"
    # Textos medidos en el árbol real tras ingresar.
    ANCLAS: tuple = ("Bienvenido,", "¿Deseas hacer una orden?")
