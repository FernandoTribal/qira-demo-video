"""El aviso de permisos de iOS que aparece después de `clearApp`: se toca
«Allow»/«Permitir», y un aviso propio de la app no se toca."""
from core.driver import Sesion


class Falso:
    def __init__(self, avisos):
        self.avisos = list(avisos)   # cada uno, la lista de botones; vacío = sin aviso
        self.tocados = []

    def execute_script(self, script, args):
        assert script == "mobile: alert"
        if args["action"] == "getButtons":
            if not self.avisos:
                raise RuntimeError("no alert open")
            return self.avisos[0]
        self.tocados.append(args["buttonLabel"])
        self.avisos.pop(0)


def test_toca_permitir_en_el_aviso_de_notificaciones():
    d = Falso([["Don’t Allow", "Allow"]])
    Sesion(d)._aceptar_permisos_del_sistema(segundos=5)
    assert d.tocados == ["Allow"]


def test_acepta_varios_avisos_seguidos():
    d = Falso([["No permitir", "Permitir"], ["Ask App Not to Track", "Allow"]])
    Sesion(d)._aceptar_permisos_del_sistema(segundos=5)
    assert d.tocados == ["Permitir", "Allow"]


def test_no_toca_un_aviso_propio_de_la_app():
    d = Falso([["Cancelar", "Cerrar sesión"]])
    Sesion(d)._aceptar_permisos_del_sistema(segundos=5)
    assert d.tocados == []


def test_sin_aviso_no_espera_todo_el_plazo():
    import time
    d = Falso([])
    antes = time.monotonic()
    Sesion(d)._aceptar_permisos_del_sistema(segundos=30)
    assert time.monotonic() - antes < 5
