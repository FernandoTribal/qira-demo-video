"""La batería que el repositorio corre sobre sí mismo (Anexo D).

Sin dispositivo, sin Appium y sin credenciales: es la primera etapa del CI. No
busca defectos del producto; impide que la suite mienta en verde. Cada prueba
dice qué evita.
"""
from __future__ import annotations

import ast
import configparser
import hashlib
import re
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
CAPAS_SIN_RELOJ = ("tests", "screens", "flows")
# El clasificador compartido (§6.4). Se copia sin editar una línea.
MD5_CLASIFICADOR = "d00fd5ec61de7e06b4a11f89748e6040"


def _py(carpeta: str) -> list:
    return sorted((RAIZ / carpeta).rglob("*.py"))


def _casos() -> list:
    casos = []
    for archivo in sorted((RAIZ / "tests").glob("test_*.py")):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        casos += [(archivo, n) for n in ast.walk(arbol)
                  if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    return casos


def _marcas(fn: ast.FunctionDef) -> set:
    nombres = set()
    for d in fn.decorator_list:
        objetivo = d.func if isinstance(d, ast.Call) else d
        if isinstance(objetivo, ast.Attribute):
            nombres.add(objetivo.attr)
    return nombres


def _importa(archivo: Path) -> set:
    modulos = set()
    for n in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            modulos |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            modulos.add(n.module.split(".")[0])
    return modulos


# ── Lo que cada caso tiene que declarar (§6.3) ─────────────────────────────

def test_hay_al_menos_un_caso():
    """Evita que todo lo demás pase en verde sobre una carpeta vacía."""
    assert _casos(), "no hay casos en tests/"


def test_todo_caso_declara_su_caso_id_en_el_docstring():
    """Evita que un caso saltado llegue al tablero como un nombre de función."""
    from core.etiquetas import CASO_ID

    sin_id = [f"{a.name}::{f.name}" for a, f in _casos()
              if not CASO_ID.match((ast.get_docstring(f) or "").strip())]
    assert not sin_id, f"sin «CP-…: título» en el docstring: {sin_id}"


def test_los_caso_id_no_se_repiten():
    """Evita que dos casos distintos se cuenten como uno en el histórico."""
    from core.etiquetas import CASO_ID

    ids = [CASO_ID.match(ast.get_docstring(f) or "").group(1)
           for _, f in _casos() if CASO_ID.match(ast.get_docstring(f) or "")]
    repetidos = sorted({i for i in ids if ids.count(i) > 1})
    assert not repetidos, f"caso_id repetidos: {repetidos}"


def test_todo_caso_tiene_severidad():
    """Evita que «fallaron 5» no se pueda leer como «1 bloqueante y 4 menores»."""
    from core.etiquetas import SEVERIDAD_POR_MARCA

    sin = [f.name for _, f in _casos()
           if not (_marcas(f) & ({"severidad"} | set(SEVERIDAD_POR_MARCA)))]
    assert not sin, f"sin severidad (marca `severidad` o una de {sorted(SEVERIDAD_POR_MARCA)}): {sin}"


def test_todo_caso_pide_v():
    """Evita que un caso se saltee la guarda de ambiente, que vive en `v`."""
    sin = [f.name for _, f in _casos() if "v" not in {a.arg for a in f.args.args}]
    assert not sin, f"no piden la fixture `v`: {sin}"


def test_lo_que_escribe_pide_permiso():
    """Evita la casilla desconectada (§13.9): marca `efectos` sin el freno."""
    sin = [f.name for _, f in _casos()
           if "efectos" in _marcas(f) and "efectos" not in {a.arg for a in f.args.args}]
    assert not sin, f"marcados `efectos` que no piden la fixture `efectos`: {sin}"


# ── Las capas (§4, §5) ─────────────────────────────────────────────────────

@pytest.mark.parametrize("carpeta", CAPAS_SIN_RELOJ)
def test_ninguna_espera_es_por_reloj(carpeta):
    """Evita el `sleep` fijo (§5.2): paga siempre el peor caso y aun así pierde
    la carrera el día que el dispositivo va lento."""
    culpables = []
    for archivo in _py(carpeta):
        for n in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Call):
                nombre = getattr(n.func, "attr", None) or getattr(n.func, "id", None)
                if nombre == "sleep":
                    culpables.append(f"{archivo.relative_to(RAIZ)}:{n.lineno}")
    assert not culpables, f"esperas por reloj: {culpables}"


def test_los_casos_no_tocan_selectores_ni_driver():
    """Evita que un caso toque un selector: es la señal de que falta algo en
    una capa de arriba, y el principio del fin de la suite (§4)."""
    prohibido = re.compile(r"find_element|AppiumBy|\bBy\.|xpath|resource-id|"
                           r"accessibility_id|_driver\b|page_source|core\.driver|from core import .*\bdriver\b")
    culpables = []
    for archivo in _py("tests"):
        if {"appium", "selenium"} & _importa(archivo):
            culpables.append(f"{archivo.name}: importa el driver")
        for i, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), 1):
            if prohibido.search(linea):
                culpables.append(f"{archivo.name}:{i}")
    assert not culpables, f"selectores o driver en tests/: {culpables}"


@pytest.mark.parametrize("capa, prohibidas", [
    ("core", {"screens", "flows", "tests", "data"}),
    ("screens", {"flows", "tests"}),
    ("flows", {"tests"}),
])
def test_la_flecha_nunca_sube(capa, prohibidas):
    """Evita que `core/` sepa de negocio o una pantalla sepa qué caso la usa."""
    culpables = [f"{a.relative_to(RAIZ)} → {sorted(_importa(a) & prohibidas)}"
                 for a in _py(capa) if _importa(a) & prohibidas]
    assert not culpables, f"importaciones hacia arriba: {culpables}"


# ── Lo que está duplicado a propósito (§13.7) ──────────────────────────────

def test_las_suites_de_run_sh_coinciden_con_el_codigo():
    """Evita que `./run.sh` rechace una suite que el código conoce, o al revés."""
    from data.suites import SUITES

    m = re.search(r'SUITES_CONOCIDAS="\s*(.+?)\s*"', (RAIZ / "run.sh").read_text(encoding="utf-8"))
    assert m and set(m.group(1).split()) == set(SUITES)


def test_la_receta_ofrece_las_suites_y_despertar_primero():
    """Evita que la corrida nocturna pida una suite que ya no existe, y que el
    «Construir ahora» de un trabajo recién creado lance una suite de verdad."""
    from data.suites import DESPERTAR, SUITES

    receta = RAIZ / "ci" / "Jenkinsfile"
    if not receta.is_file():
        receta = RAIZ / "ci" / "Jenkinsfile.plantilla"
    m = re.search(r"choice\(\s*name:\s*'SUITE'\s*,\s*choices:\s*\[(.+?)\]",
                  receta.read_text(encoding="utf-8"), re.S)
    assert m, "no encontré el desplegable SUITE en la receta"
    ofrecidas = re.findall(r"'([^']+)'", m.group(1))
    assert ofrecidas[0] == DESPERTAR
    assert set(ofrecidas) == set(SUITES) | {DESPERTAR}


def test_el_clasificador_es_el_compartido_sin_editar():
    """Evita que «problema de ambiente» deje de significar lo mismo entre suites."""
    digest = hashlib.md5((RAIZ / "allure-categories.json").read_bytes()).hexdigest()
    assert digest == MD5_CLASIFICADOR


# ── Los borradores de QIRA nunca corren ────────────────────────────────────

def test_pytest_ini_colecta_solo_tests():
    ini = configparser.ConfigParser()
    ini.read(RAIZ / "pytest.ini", encoding="utf-8")
    assert ini["pytest"]["testpaths"].split() == ["tests"]
    assert "borradores" in ini["pytest"]["norecursedirs"].split()


def test_los_borradores_no_se_colectan():
    """Evita que un borrador de QIRA —sin revisar, quizá sin selectores
    reales— entre a una corrida y al tablero como si fuera un caso."""
    salida = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-p", "no:cacheprovider", "-o", "addopts="],
        cwd=RAIZ, capture_output=True, text=True, timeout=120)
    assert salida.returncode == 0, salida.stdout + salida.stderr
    assert "borradores" not in salida.stdout


# ── La configuración no inventa nada ───────────────────────────────────────

def test_una_credencial_que_falta_se_nombra(monkeypatch):
    """Evita el valor por omisión silencioso: una cuenta inventada entra con
    otra identidad y pasa en verde."""
    from core import config

    monkeypatch.delenv(f"{config.PREFIJO}_NOEXISTE_USUARIO", raising=False)
    monkeypatch.delenv(f"{config.PREFIJO}_NOEXISTE_CLAVE", raising=False)
    with pytest.raises(config.ErrorDeConfiguracion) as e:
        config.credencial("noexiste")
    assert f"{config.PREFIJO}_NOEXISTE_USUARIO" in str(e.value)
    assert f"{config.PREFIJO}_NOEXISTE_CLAVE" in str(e.value)


def test_las_urls_siguen_la_convencion(monkeypatch):
    from core import config

    monkeypatch.setenv(f"{config.PREFIJO}_URL", "https://principal.ejemplo/")
    monkeypatch.setenv(f"{config.PREFIJO}_ADMIN_URL", "https://admin.ejemplo")
    assert config.url() == "https://principal.ejemplo"
    assert config.url("admin") == "https://admin.ejemplo"
    monkeypatch.delenv(f"{config.PREFIJO}_API_URL", raising=False)
    with pytest.raises(config.ErrorDeConfiguracion, match=f"{config.PREFIJO}_API_URL"):
        config.url("api")


def test_la_etiqueta_de_plataforma_sale_de_la_corrida(monkeypatch):
    """Evita que una corrida en Android llegue al tablero como `app-ios`, o al
    revés: la etiqueta se lee de `PLATAFORMA` al colectar, nunca se escribe fija."""
    from core import config
    from data.suites import sistema_por_fixture

    for plataforma in config.PLATAFORMAS:
        monkeypatch.setattr(config, "PLATAFORMA", plataforma)
        assert sistema_por_fixture() == {"app": f"app-{plataforma}"}
