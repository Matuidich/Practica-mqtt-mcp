# Configuración compartida

`.env` existente es la fuente local. Se conserva su UUID v4, broker, prefijo,
intervalos y client_id derivados. El entorno del proceso no sobrescribe valores.
`integrated` reutiliza MQTT_CLIENT_ID del rol FIRMWARE; no requiere nuevas claves
ni cambiar la configuración. Las identidades sensor/actuator se conservan para
los entornos anteriores.
Formato deliberadamente reducido KEY=VALUE, sin comillas, expansión ni claves
extra; usar Python 3.11 y biblioteca estándar.

## Inicializar y sincronizar

`python -B -m iot_shared init` crea `.env` con UUID v4 solo si no existe. Si existe,
lo conserva. Para este proyecto ya inicializado utilizar:

```powershell
python -B -m iot_shared sync
python -B -m iot_shared check
python -B -m iot_shared show
```

`sync` actualiza exclusivamente `firmware/include/mqtt_config.local.h` y
`config/mobile.local.json`. `check` detecta desajustes sin repararlos. No se edita
la cabecera generada a mano ni se copian tópicos en distintos componentes.

Se añaden las constantes MQTT_TOPIC_LED_COMMAND y MQTT_TOPIC_LED_STATE al exportar.
El prefijo y telemetry/distance permanecen iguales. Las claves SERVO_MIN_ANGLE y
SERVO_MAX_ANGLE del `.env` y sus exportaciones se mantienen para no migrar ni
sobrescribir configuración histórica; no regulan los LEDs. Los tópicos servo
siguen reservados a su contrato previo.

## Wi-Fi y salidas locales

`device_config.local.h` contiene Wi-Fi y pines y permanece ignorado por Git.
No reemplazarlo por la plantilla si ya existe. Sin esa copia se compila con
SSID vacío y no se intenta Wi-Fi. Las opciones LED se definen mediante macros
para que una copia local antigua siga funcionando sin cambios y quede bloqueada:

```cpp
#define LED_WIRING_CONFIRMED false
#define LED_RED_PIN 25
#define LED_YELLOW_PIN 26
#define LED_GREEN_PIN 27
```

La plantilla las incluye; LedSettings aporta los mismos valores de respaldo.
Solo el usuario cambia la bandera a true en su copia después de verificar el
[cableado](esp32-integrado.md). La bandera antigua SG90 no habilita LEDs. No hay cambios
automáticos en SSID, contraseña ni pines reales.

`.gitignore` excluye `.env`, copias locales, cabeceras derivadas, claves privadas,
configuración personal y productos de compilación. Nunca incluir credenciales
reales en plantillas, documentación o pruebas.

## Referencia móvil

`config/mobile.config.example.json` usa un marcador UUID. Su copia derivada
`config/mobile.local.json` contiene el prefijo local real y no se versiona.
Incluye gauge de distancia, led_control con tres interruptores y led_confirmation
con los tres booleanos y correlación command_id. Omitir un color lo conserva;
exclusividad y apagado total envían los tres. No es una aplicación construida ni
un formato de importación garantizado por una herramienta móvil específica.

## MCP y simulador

Ambos reutilizan Settings y los mensajes comunes. MCP implementa FastMCP por
STDIO, transporte Paho, caché con antigüedad, timeouts y correlación de órdenes LED.
Su entrada busca `.env` mediante la ruta absoluta del proyecto, sin sobrescrituras
del proceso. `--check-offline` usa un doble MQTT y configuración ficticia; el
arranque normal sí inicia una conexión MQTT. El simulador conserva su modelo local
y su entrada de red aún está pendiente. Ver [guía MCP](../mcp-server/README.md).
El registro en Codex se documenta para ejecución manual; no se ha modificado su
configuración personal ni conectado MCP al broker durante las pruebas locales.
