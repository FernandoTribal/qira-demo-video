"""El aparato propio y el de la granja (`DISPOSITIVOS`), sin abrir nada.

Lo que se vigila es el contrato con QIRA y con la receta: que una app ya subida
a Sauce llegue a Appium tal cual, que las capacidades de quien arma se mezclen
sin perder las que no se negocian, y que sin `DISPOSITIVOS=sauce` todo siga
como siempre.
"""
from __future__ import annotations

import pytest

from core import config, driver


@pytest.fixture
def sauce(monkeypatch):
    """Una corrida contra Sauce, puesta a mano sobre lo que ya se leyó."""
    for nombre, valor in {
        "DISPOSITIVOS": "sauce", "EN_SAUCE": True, "SAUCE_REGION": "us-west-1",
        "SAUCE_USERNAME": "usuario-de-prueba", "SAUCE_ACCESS_KEY": "clave-de-prueba",
        "SAUCE_BUILD": "", "APPIUM_CAPACIDADES": "", "APPIUM_DE_QORA": False,
    }.items():
        monkeypatch.setattr(config, nombre, valor)
    return monkeypatch


# ── El binario ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("valor", [
    "storage:0123abcd-4567-89ef-0123-456789abcdef",
    "storage:filename=app-1.2.3.apk",
    "https://descargas.ejemplo/app-1.2.3.apk",
    "http://interno.ejemplo/app.ipa",
])
def test_lo_que_no_es_un_archivo_de_esta_maquina_pasa_tal_cual(monkeypatch, valor):
    """Evita que la app ya subida a la granja se lea como «el archivo no está»
    y la sesión abra un emulador vacío."""
    monkeypatch.setenv(f"{config.PREFIJO}_APK", valor)
    assert config._binario(f"{config.PREFIJO}_APK") == valor


def test_una_ruta_que_no_existe_sigue_siendo_vacia(monkeypatch):
    """Lo de siempre: un clon limpio no trae el APK y la app ya está instalada."""
    monkeypatch.setenv(f"{config.PREFIJO}_APK", "apk/no-existe-en-ningun-lado.apk")
    assert config._binario(f"{config.PREFIJO}_APK") == ""


def test_el_binario_declarado_es_el_de_la_plataforma(monkeypatch):
    monkeypatch.setenv(f"{config.PREFIJO}_APK", "storage:a")
    monkeypatch.setenv(f"{config.PREFIJO}_IPA", "storage:i")
    monkeypatch.setattr(config, "ES_IOS", False)
    assert config.binario_declarado() == (f"{config.PREFIJO}_APK", "storage:a")
    monkeypatch.setattr(config, "ES_IOS", True)
    assert config.binario_declarado() == (f"{config.PREFIJO}_IPA", "storage:i")


# ── La mezcla de capacidades ───────────────────────────────────────────────

def test_la_mezcla_lleva_lo_de_quien_arma_y_lo_que_no_se_negocia(sauce):
    sauce.setattr(config, "APPIUM_CAPACIDADES",
                  '{"appium:deviceName":"Android GoogleAPI Emulator",'
                  '"appium:platformVersion":"14.0","appium:newCommandTimeout":30}')
    sauce.setattr(config, "SAUCE_BUILD", "PROY-123 #42")
    caps = driver.capacidades_sauce("humo · android")
    assert caps["appium:deviceName"] == "Android GoogleAPI Emulator"
    assert caps["appium:platformVersion"] == "14.0"
    # Lo que no se negocia gana aunque venga otra cosa en el JSON.
    assert caps["appium:newCommandTimeout"] == 300
    assert caps["sauce:options"] == {
        "username": "usuario-de-prueba", "accessKey": "clave-de-prueba",
        "name": "humo · android", "build": "PROY-123 #42", "idleTimeout": 300}


def test_un_sauce_options_del_json_se_completa_y_no_se_pisa(sauce):
    """Evita que un `sauce:options` puesto por quien arma (p. ej. `appiumVersion`)
    se pierda, y que traiga credenciales que ganen a las de la credencial."""
    sauce.setattr(config, "APPIUM_CAPACIDADES",
                  '{"sauce:options":{"appiumVersion":"latest","name":"a mano",'
                  '"username":"otro"}}')
    opciones = driver.capacidades_sauce("humo · ios")["sauce:options"]
    assert opciones["appiumVersion"] == "latest"
    assert opciones["name"] == "a mano"
    assert opciones["username"] == "usuario-de-prueba"
    assert "build" not in opciones  # sin SAUCE_BUILD no se inventa uno


def test_las_capacidades_mezcladas_no_dejan_udid(sauce):
    """Con la granja el aparato lo eligen las capacidades: un UDID de la mesa
    local que quedó en el `.env` pediría uno que allá no existe."""
    pytest.importorskip("appium")
    sauce.setattr(config, "ANDROID_UDID", "emulator-5554")
    sauce.setattr(config, "ES_IOS", False)
    opciones = driver._opciones_android()
    opciones.load_capabilities(driver.capacidades_sauce())
    caps = opciones.to_capabilities()
    assert "appium:udid" not in caps
    assert caps["appium:newCommandTimeout"] == 300
    assert caps["platformName"].lower() == "android"


@pytest.mark.parametrize("crudo", ['{"appium:deviceName":', '["no", "es", "objeto"]'])
def test_un_json_roto_se_dice_antes_de_abrir(sauce, crudo):
    """Evita que una capacidad mal escrita se ignore y la granja dé OTRO
    aparato, que se entregaría como el pedido."""
    sauce.setattr(config, "APPIUM_CAPACIDADES", crudo)
    with pytest.raises(config.ErrorDeConfiguracion, match="APPIUM_CAPACIDADES"):
        config.capacidades_extra()
    assert any("APPIUM_CAPACIDADES" in f for f in config.faltantes())


# ── Lo que se exige con cada aparato ───────────────────────────────────────

def test_con_sauce_ios_no_pide_udid_pero_si_credenciales_y_app(sauce):
    sauce.setattr(config, "PLATAFORMA", "ios")
    sauce.setattr(config, "ES_IOS", True)
    sauce.setattr(config, "BUNDLE_ID", "com.ejemplo.demo")
    sauce.setattr(config, "IOS_UDID", "")
    sauce.setattr(config, "IPA", "")
    sauce.setattr(config, "SAUCE_ACCESS_KEY", "")
    faltan = config.faltantes()
    assert "IOS_UDID" not in faltan
    assert "SAUCE_ACCESS_KEY" in faltan
    assert f"{config.PREFIJO}_IPA" in faltan


def test_sin_sauce_ios_sigue_pidiendo_el_udid(monkeypatch):
    monkeypatch.setattr(config, "DISPOSITIVOS", "local")
    monkeypatch.setattr(config, "EN_SAUCE", False)
    monkeypatch.setattr(config, "APPIUM_CAPACIDADES", "")
    monkeypatch.setattr(config, "PLATAFORMA", "ios")
    monkeypatch.setattr(config, "ES_IOS", True)
    monkeypatch.setattr(config, "BUNDLE_ID", "com.ejemplo.demo")
    monkeypatch.setattr(config, "IOS_UDID", "")
    assert config.faltantes() == ["IOS_UDID"]


def test_un_modo_de_dispositivos_raro_no_se_corrige(monkeypatch):
    monkeypatch.setattr(config, "DISPOSITIVOS", "saucelabs")
    monkeypatch.setattr(config, "PLATAFORMA", "android")
    assert config.faltantes()[0].startswith("DISPOSITIVOS")


# ── Lo que se ve de la sesión ──────────────────────────────────────────────

class DriverDoble:
    session_id = "abc123"

    def __init__(self):
        self.scripts = []

    def execute_script(self, script, *args):
        self.scripts.append(script)


@pytest.mark.parametrize("region, sitio", [
    ("us-west-1", "app.saucelabs.com"),
    ("eu-central-1", "app.eu-central-1.saucelabs.com"),
])
def test_el_enlace_a_la_sesion_sale_de_la_region(sauce, region, sitio):
    sauce.setattr(config, "SAUCE_REGION", region)
    assert driver.enlace_sesion(DriverDoble()) == f"https://{sitio}/tests/abc123"


def test_el_resultado_se_marca_solo_en_sauce(sauce):
    d = DriverDoble()
    driver.marcar_resultado(d, False)
    assert d.scripts == ["sauce:job-result=failed"]
    sauce.setattr(config, "EN_SAUCE", False)
    driver.marcar_resultado(d, True)
    assert d.scripts == ["sauce:job-result=failed"]
    assert driver.enlace_sesion(d) == ""


def test_en_sauce_no_se_graba_video_aca(sauce):
    """La granja graba el suyo: grabar acá pagaría dos veces y, en iOS, pediría
    un ffmpeg que allá no hay. Tampoco se avisa: no es una falta."""
    from core import evidencia

    class SesionQueNoDebeGrabar:
        def empezar_grabacion(self, limite_s):
            raise AssertionError("no tenía que grabar")

    sauce.setattr(config, "EVIDENCIA_VIDEO", "siempre")
    assert evidencia._empezar_video(SesionQueNoDebeGrabar()) is False
    assert not evidencia._SIN_VIDEO["motivo"]


def test_con_tunel_la_sesion_sale_por_el(sauce):
    sauce.setattr(config, "SAUCE_TUNEL", "cliente-uat")
    sauce.setattr(config, "SAUCE_TUNEL_DUENO", "cuenta-servicio")
    opciones = driver.capacidades_sauce("x")["sauce:options"]
    assert opciones["tunnelName"] == "cliente-uat"
    assert opciones["tunnelOwner"] == "cuenta-servicio"


def test_sin_tunel_no_se_nombra_ninguno(sauce):
    sauce.setattr(config, "SAUCE_TUNEL", "")
    sauce.setattr(config, "SAUCE_TUNEL_DUENO", "cuenta-servicio")
    opciones = driver.capacidades_sauce("x")["sauce:options"]
    assert "tunnelName" not in opciones and "tunnelOwner" not in opciones


class _Respuesta:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_el_resultado_se_marca_por_la_api_con_la_sesion(sauce):
    pedidos = []
    sauce.setitem(driver.DISPOSITIVO, "sesion_sauce", "abc123")
    assert driver.marcar_por_api(False, _abrir=lambda p, timeout: pedidos.append(p) or _Respuesta())
    p = pedidos[0]
    assert p.get_method() == "PUT"
    assert p.full_url == "https://api.us-west-1.saucelabs.com/rest/v1/usuario-de-prueba/jobs/abc123"
    assert p.data == b'{"passed": false}'


def test_sin_sesion_de_sauce_no_marca_nada(sauce):
    sauce.setitem(driver.DISPOSITIVO, "sesion_sauce", None)
    assert driver.marcar_por_api(True, _abrir=lambda *a, **k: 1 / 0) is False


def test_si_la_api_falla_no_lanza_ni_muestra_la_llave(sauce, capsys):
    sauce.setitem(driver.DISPOSITIVO, "sesion_sauce", "abc123")

    def falla(*_a, **_k):
        raise OSError("sin red")
    assert driver.marcar_por_api(True, _abrir=falla) is False
    assert "clave-de-prueba" not in capsys.readouterr().out


# ── Con un aparato prestado por QORA ───────────────────────────────────────

@pytest.fixture
def prestamo(sauce):
    """Sauce a través de un préstamo de QORA: la cuenta la pone QORA."""
    sauce.setattr(config, "APPIUM_DE_QORA", True)
    sauce.setattr(config, "SAUCE_USERNAME", "")
    sauce.setattr(config, "SAUCE_ACCESS_KEY", "")
    sauce.setenv("APPIUM_URL", "http://qora.ejemplo:4330/wd/" + "a" * 48)
    return sauce


def test_con_un_prestamo_en_sauce_no_se_pide_la_cuenta(prestamo):
    prestamo.setattr(config, "PLATAFORMA", "android")
    prestamo.setattr(config, "ES_IOS", False)
    prestamo.setattr(config, "PAQUETE", "com.ejemplo.demo")
    prestamo.setattr(config, "ACTIVIDAD", ".Principal")
    prestamo.setattr(config, "APK", "storage:0123abcd-4567-89ef-0123-456789abcdef")
    assert config.faltantes() == []
    # La app sigue haciendo falta: el emulador de la granja nace vacío.
    prestamo.setattr(config, "APK", "")
    assert config.faltantes() == [f"{config.PREFIJO}_APK"]


def test_con_un_prestamo_sin_su_direccion_se_reclama(prestamo):
    """Sin `APPIUM_URL` se iría al hub de Sauce sin cuenta: se dice antes."""
    prestamo.delenv("APPIUM_URL")
    prestamo.setattr(config, "PLATAFORMA", "android")
    prestamo.setattr(config, "ES_IOS", False)
    prestamo.setattr(config, "PAQUETE", "com.ejemplo.demo")
    prestamo.setattr(config, "ACTIVIDAD", ".Principal")
    prestamo.setattr(config, "APK", "storage:a")
    assert config.faltantes() == ["APPIUM_URL"]


def test_con_un_prestamo_no_viajan_credenciales(prestamo):
    prestamo.setattr(config, "APPIUM_CAPACIDADES",
                     '{"sauce:options":{"username":"marcador","accessKey":"marcador","appiumVersion":"latest"}}')
    opciones = driver.capacidades_sauce("humo · android")["sauce:options"]
    assert "username" not in opciones and "accessKey" not in opciones
    assert opciones["appiumVersion"] == "latest"
    assert opciones["idleTimeout"] == 300


def test_con_un_prestamo_no_se_marca_por_la_api_pero_si_por_el_driver(prestamo, capsys):
    """La API de Sauce pide la cuenta, que es de QORA: con marcadores dejaba un
    error en el registro. El `sauce:job-result` por el driver sí pasa."""
    prestamo.setattr(config, "SAUCE_USERNAME", "qora")
    prestamo.setattr(config, "SAUCE_ACCESS_KEY", "la-pone-qora")
    prestamo.setitem(driver.DISPOSITIVO, "sesion_sauce", "abc123")
    assert driver.marcar_por_api(False, _abrir=lambda *a, **k: 1 / 0) is False
    assert "[sauce]" not in capsys.readouterr().out
    d = DriverDoble()
    driver.marcar_resultado(d, False)
    assert d.scripts == ["sauce:job-result=failed"]
