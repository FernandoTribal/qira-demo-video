# App móvil · Demo · pruebas automatizadas de la app

Suite móvil de App móvil · Demo (`APP-MOVIL-DEMO`): Python · pytest · Appium, Android
(UiAutomator2) e iOS (XCUITest). Sigue `GUIA_PROYECTO_NUEVO.md`, del repositorio
de guías (no se copia acá). Lo abierto está en [`docs/PENDIENTE.md`](docs/PENDIENTE.md).

## Correr

```bash
./run.sh --preparar           # una vez: arma .venv e instala requirements.txt
./run.sh --unitarias          # la batería de coherencia: sin teléfono ni credenciales
./run.sh humo                 # lo mínimo; también: regresion (por omisión), completa
PLATAFORMA=ios ./run.sh humo  # contra un iPhone
./run.sh completa --efectos   # incluye lo que ESCRIBE en el producto
./run.sh --suites             # qué suites hay
```

Hace falta un servidor de Appium levantado (`appium`, por omisión en
`http://127.0.0.1:4723`) y el teléfono conectado. Si Appium no contesta, la
corrida no reporta defectos: salta todos los casos con `ambiente:` y lo dice.

Lo que queda en `reports/allure-results/` es lo que se entrega: el crudo, más
`suite.json`, `environment.properties`, `categories.json` y `executor.json`.

## Dónde van las credenciales

En `.env` (común) y `.env.<AMBIENTE>` (lo propio de ese ambiente, que pisa a
`.env`). Ninguno se versiona; `.env.ejemplo` dice qué variables hay. En el CI
llegan como el secreto `app-movil-demo-dotenv`.

| Variable | Qué es |
|---|---|
| `AMBIENTE` | contra qué ambiente se corre |
| `PLATAFORMA` | `android` o `ios` (la pone `run.sh`) |
| `APP_PAQUETE` · `APP_ACTIVIDAD` · `APP_APK` | la app en Android |
| `APP_BUNDLE_ID` · `IOS_UDID` | la app y el teléfono en iOS |
| `APPIUM_URL` · `ANDROID_UDID` | el servidor y el teléfono |
| `APP_URL` · `APP_<CLAVE>_URL` | los sistemas web que la suite también toca |
| `APP_<ROL>_USUARIO` · `APP_<ROL>_CLAVE` | una cuenta por rol |
| `EVIDENCIA_VIDEO` | `fallos` (por omisión) · `siempre` · `nunca`: cuándo va el video al reporte (ver abajo) |

Una credencial que falta no tiene valor por omisión: `config.credencial(rol)`
falla nombrando la variable.

## Cuando un caso falla

El reporte de Allure trae con qué entenderlo, sin que el caso lo pida: lo pone
`core/evidencia.py` desde la fixture `app` y un hook de `conftest.py`.

- **Captura y árbol de la pantalla** (el XML de Appium), tomados en el momento
  del fallo, sea en la preparación, en el caso o en el cierre. El árbol dice
  por qué no se encontró un elemento: otro texto, otro id, otra pantalla.
- **Video** del caso entero, de la app abierta al cierre. Con `fallos` se graba
  cada caso y sólo se adjunta si falló; `siempre` lo deja también en los
  verdes; `nunca` no graba. Corta a los 10 minutos.
- Una verificación de `v` que falla ya trae su captura del momento: no se
  repite. Un crítico suma el árbol.

Si Appium no puede grabar (en iOS hace falta `ffmpeg` en la máquina de Appium),
la corrida sigue sin video y lo avisa una vez en el resumen de pytest. Nada de
esto hace fallar un caso ni tapa el error original.

## Las capas

`tests/` → `flows/` → `screens/` → `core/`, y la flecha nunca sube. Un caso no
toca un selector ni el driver; pide lo que necesita en su firma (`app`, `v`) y
verifica con `v`, que acumula y falla una sola vez al final. Cada caso lleva
`CP-…: título` como primera línea del docstring.

## `borradores/qira/`

Lo escribe QIRA a partir de los casos diseñados allí. **Nunca corre**: pytest
sólo colecta `tests/`, y `./run.sh --unitarias` lo comprueba. Un borrador se lee,
se reescribe con las pantallas y flujos del proyecto y recién entonces entra a
`tests/`. Sólo `borradores/qira/mapa.json` se versiona; el resto se regenera.
