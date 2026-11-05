"""HU-DEMO-01 (LTQ-1025): inicio de sesión — casos de QIRA."""
from __future__ import annotations

import json
import re

import pytest

from core import config
from flows.acceso import llegar_a_login
from screens.inicio import InicioConSesion

_FILAS = json.loads((config.RAIZ / "datos/qira/CP-DEMO-09.json").read_text(encoding="utf-8"))["filas"]


def _valor(clave: str, valor: str) -> str:
    """Una celda `{rol: <rol>}` es la cuenta de ese rol, no un texto."""
    m = re.fullmatch(r"\{\s*rol\s*:\s*([\w-]+)\s*\}", valor.strip())
    if not m:
        return valor
    try:
        usuario, contrasena = config.credencial(m.group(1))
    except config.ErrorDeConfiguracion as e:
        pytest.skip(f"ambiente: {e}")
    return contrasena if clave.lower() in ("clave", "contraseña", "contrasena", "password") else usuario


@pytest.mark.func("Inicio de sesión")
@pytest.mark.severidad("normal")
@pytest.mark.parametrize("fila", _FILAS, ids=[f["nombre"] for f in _FILAS])
def test_cp_demo_09_comprobar_que_un_correo_sin_dominio_ni(app, sin_sesion, v, fila):
    """CP-DEMO-09: Comprobar que un correo sin dominio ni extensión (usuario@) es rechazado con el mensaje «Escribe un correo válido.» e impide continuar"""
    datos = {k: _valor(k, x) for k, x in fila["valores"].items()}
    login = llegar_a_login(app)
    login.escribir_correo(datos["correo"])
    login.escribir_contrasena(datos["contrasena"])
    login.marcar_terminos()
    login.quitar_foco_del_correo()

    v.que(login.esperar_mensaje_de_correo(), fila["esperado"],
          esperado=login.MENSAJE_CORREO, obtenido="el mensaje no aparece")
    v.que(not login.ingresa_habilitado(), "El botón «Ingresa» permanece deshabilitado",
          esperado="deshabilitado", obtenido="habilitado")


@pytest.mark.func("Inicio de sesión")
@pytest.mark.severidad("critical")
def test_cp_demo_11_comprobar_que_al_tocar_ingresa_con_un_c(app, sin_sesion, v):
    """CP-DEMO-11: Comprobar que al tocar «Ingresa» con un correo de formato válido, una contraseña que coincide con la cuenta registrada y la casilla de términos marcada, la aplicación navega a la pantalla de Inicio con la sesión del usuario abierta"""
    # El correo es la cuenta del rol `cliente` (config.credencial): no se escribe un usuario literal.
    correo, contrasena = config.credencial("cliente")
    login = llegar_a_login(app)
    login.escribir_correo(correo)
    login.escribir_contrasena(contrasena)
    login.marcar_terminos()
    login.tocar_ingresa()

    salio = login.se_va()
    v.que(salio, "La aplicación sale de la pantalla de login",
          esperado="sin login en pantalla", obtenido="sigue el login")
    v.cargada(InicioConSesion(app))


@pytest.mark.func("Inicio de sesión")
@pytest.mark.severidad("critical")
def test_cp_demo_03_comprobar_que_el_boton_ingresa_permanec(app, sin_sesion, v):
    """CP-DEMO-03: Comprobar que el botón «Ingresa» permanece deshabilitado cuando el correo tiene formato válido pero la contraseña está vacía, aunque los términos estén marcados"""
    # Dato de QIRA (datos.correoValido): sólo se prueba su formato; no se inicia sesión con él.
    correo_valido = "cliente@dominio.com"
    login = llegar_a_login(app)
    login.escribir_correo(correo_valido)
    login.marcar_terminos()

    v.que(not login.ingresa_habilitado(), "El botón «Ingresa» se muestra deshabilitado",
          esperado="deshabilitado", obtenido="habilitado")
    login.tocar_ingresa()
    v.que(not login.se_va(tope=3.0), "El botón «Ingresa» no responde al toque",
          esperado="sigue el login", obtenido="la aplicación salió del login")
