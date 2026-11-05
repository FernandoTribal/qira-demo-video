"""Recorridos para llegar al login."""
from __future__ import annotations

from screens.bienvenida import Bienvenida, DialogoNotificaciones


def llegar_a_bienvenida(app) -> Bienvenida:
    """Acepta el diálogo de notificaciones si aparece y espera la bienvenida."""
    bienvenida = Bienvenida(app)
    dialogo = DialogoNotificaciones(app)
    arbol = dialogo.esperar(
        lambda a: dialogo.en_el_arbol(a) or bienvenida.en_el_arbol(a),
        que="el diálogo de notificaciones o la bienvenida")
    if dialogo.en_el_arbol(arbol):
        dialogo.permitir()
        bienvenida.esperar(bienvenida.en_el_arbol, que="la bienvenida")
    return bienvenida


def llegar_a_login(app):
    """De la app recién abierta a la pantalla de login (Saltar tutorial)."""
    from screens.login import Login

    llegar_a_bienvenida(app).saltar_tutorial()
    login = Login(app)
    login.esperar(login.en_el_arbol, que="la pantalla de login")
    return login
