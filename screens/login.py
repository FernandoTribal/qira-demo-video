"""Pantalla de login."""
from __future__ import annotations

from core.pantalla import Screen


class Login(Screen):
    NAME = "Login"
    ANCLAS: tuple = ("Ingresa", "términos y condiciones")

    MENSAJE_CORREO = "Escribe un correo válido."

    # Los dos campos de texto no traen identificador, nombre ni etiqueta en iOS
    # (medido en el árbol real): se toman por clase y orden en pantalla. El
    # primero es Correo y el segundo Contraseña.
    def _campo(self, posicion: int):
        campos = [n for n in self.arbol().nodos if n.clase.endswith("TextField")]
        if len(campos) <= posicion:
            raise LookupError(f"no hay el campo de texto n.º {posicion + 1} en «{self.NAME}»")
        return campos[posicion]

    def _escribir_en(self, posicion: int, texto: str) -> None:
        self._sesion.tocar(*self._campo(posicion).centro)
        self._sesion.escribir(texto)
        # La barra del teclado de iOS cubre la casilla de términos mientras
        # está abierto. En el árbol «Aceptar» es una barra a todo el ancho (no
        # un botón; tocarla en el centro no hace nada): el botón de verdad está
        # en su extremo derecho, que se deriva de la caja de la barra.
        self._sesion.ocultar_teclado()
        barra = self.arbol().uno("Aceptar", exacto=True)
        if barra is not None:
            x1, y1, x2, y2 = barra.caja
            self._sesion.tocar(x2 - 40, (y1 + y2) // 2)
            self.esperar(lambda a: not a.hay("Aceptar", exacto=True),
                         que="que se cierre el teclado", tope=5.0)

    def escribir_correo(self, texto: str) -> None:
        self._escribir_en(0, texto)

    def escribir_contrasena(self, texto: str) -> None:
        self._escribir_en(1, texto)

    def marcar_terminos(self) -> None:
        interruptor = next((n for n in self.arbol().nodos if n.clase.endswith("Switch")), None)
        if interruptor is None:
            raise LookupError(f"no está la casilla de términos en «{self.NAME}»")
        self._sesion.tocar(*interruptor.centro)

    def quitar_foco_del_correo(self) -> None:
        """Toca el texto del encabezado, que no es un control."""
        self.tocar("La mejor calidad a un clic", exacto=True)

    def tocar_ingresa(self) -> None:
        self.tocar("Ingresa", exacto=True)

    def mensaje_de_correo_visible(self) -> bool:
        return self.arbol().hay(self.MENSAJE_CORREO)

    def esperar_mensaje_de_correo(self, *, tope: float = 5.0) -> bool:
        """¿Aparece el mensaje de correo inválido dentro del tope? No lanza."""
        try:
            self.esperar(lambda a: a.hay(self.MENSAJE_CORREO), que="el mensaje de correo inválido",
                         tope=tope)
        except TimeoutError:
            return False
        return True

    def se_va(self, *, tope: float = 15.0) -> bool:
        """¿Desaparece el login dentro del tope? Devuelve un hecho; no lanza."""
        try:
            self.esperar(lambda a: not self.en_el_arbol(a), que="que el login desaparezca", tope=tope)
        except TimeoutError:
            return False
        return True

    def ingresa_habilitado(self) -> bool:
        """`Nodo` no lleva el estado habilitado: se lee del árbol crudo."""
        import xml.etree.ElementTree as ET

        for el in ET.fromstring(self._sesion.fuente()).iter():
            if el.attrib.get("name") == "Ingresa" and el.attrib.get("type", "").endswith("Button"):
                return el.attrib.get("enabled") != "false"
        raise LookupError(f"no está el botón «Ingresa» en «{self.NAME}»")
