# SIS-234: ESP32, MQTT y MCP

**Integrantes:** Mateo Rojas y Lucia Escobar.

El prototipo real utiliza **un ESP32 DOIT DevKit V1**, entorno `integrated`,
un HC-SR04 y tres LEDs (rojo, amarillo y verde). Publica distancias y recibe
órdenes LED con una sesión MQTT; IoT MQTT Panel y el servidor MCP permiten
consultar la telemetría y controlar los LEDs.

El grupo verificó físicamente el gauge móvil, los botones rojo/amarillo/verde y
apagar todos, y las consultas y órdenes en lenguaje natural desde Codex.
Fue una demostración manual, sin registro audiovisual guardado.

## Tópicos MQTT y mensajes

Broker: `broker.hivemq.com:1883`, MQTT 3.1.1 sobre TCP, QoS 0, sin retain.
Cada cliente utiliza un identificador distinto. Estos son los tópicos del
prefijo actual; los JSON son ejemplos de formato, no mediciones adicionales.

| Tópico completo | Publica → recibe | Ejemplo JSON |
| --- | --- | --- |
| `sis234/2026/3a91a2d6-974c-4879-b67e-3ba4a37c201d/telemetry/distance` | ESP32 → móvil y MCP | `{"distance_cm":42.5,"device_id":"sensor-01","uptime_ms":12345}` |
| `sis234/2026/3a91a2d6-974c-4879-b67e-3ba4a37c201d/commands/leds` | Móvil o MCP → ESP32 | `{"command_id":"led-001","leds":{"red":true,"yellow":false,"green":false}}` |
| `sis234/2026/3a91a2d6-974c-4879-b67e-3ba4a37c201d/state/leds` | ESP32 → móvil y MCP | `{"leds":{"red":true,"yellow":false,"green":false},"command_id":"led-001","device_id":"actuator-01","uptime_ms":12345,"status":"applied"}` |

Usar un `command_id` nuevo por orden; la confirmación devuelve el mismo ID y
los tres colores. Omitir un color en la orden conserva su estado. `applied`
confirma niveles GPIO lógicos, no luz medida ni cableado comprobado.

## Herramientas MCP expuestas

Nombres y parámetros verificados en [server.py](mcp-server/iot_mcp/server.py)
y [tools.py](mcp-server/iot_mcp/tools.py).

| Nombre | Parámetros obligatorios | Propósito |
| --- | --- | --- |
| `get_last_distance` | Ninguno | Consultar la última distancia, su edad y vigencia |
| `get_led_state` | Ninguno | Consultar el último estado LED observado |
| `set_led` | `color: str`, `on: bool` | Encender o apagar un LED sin cambiar los demás |
| `set_leds` | `changes: dict[str, bool]` | Cambiar uno, dos o tres colores en una orden |
| `set_only_led` | `color: str` | Encender solo un color y apagar los demás |
| `turn_off_all_leds` | Ninguno | Apagar los tres LEDs |

Colores válidos: `red`, `yellow`, `green`. Las cuatro herramientas de escritura
admiten además `command_id: str` opcional (se genera si se omite) y
`timeout_s: float` (5 s por defecto; `0 < timeout_s <= 30`). Esperan una
confirmación correlacionada; una publicación aceptada no demuestra su aplicación.

## Cinco requisitos no funcionales

| Requisito | Valor u objetivo declarado | Estado real de verificación |
| --- | --- | --- |
| Estabilidad | 600 s continuos | Cumplida en la captura: 600.016 s, 600 lecturas válidas y únicas; 0 silencios mayores de 3 s, interrupciones del observador o duplicados; ningún reinicio detectado por uptime |
| Frecuencia | Aproximadamente 1 Hz (intervalo de referencia: 1000 ms); mínimo formal aún por declarar | Observada: 0.999973 Hz; 60 lecturas en cada uno de los 10 minutos completos |
| Exactitud | Comparar con cinta métrica; error y umbral aún sin cuantificar | Pendiente de medición física |
| Tiempo de respuesta | Respuesta física ≤ 1 s | Respuesta visual prácticamente inmediata al encender y apagar los LEDs desde IoT MQTT Panel; observación manual durante el uso real |
| Reconexión WiFi/MQTT | Restablecer automáticamente WiFi y MQTT sin intervención manual en el ESP32; tiempo por medir | Pendiente de prueba real |

No se usó cronómetro ni video para la respuesta: **el cumplimiento cuantitativo
de ≤ 1 s no está demostrado**. La medición instrumental sigue pendiente.
Estabilidad y frecuencia corresponden a la captura del 2026-10-29:
[evidencia original estabilidad-02](evidence/estabilidad-02/summary.json).
Se midieron recepciones MQTT, no la pérdida exacta de paquetes.

## Configuración y ejecución manual

Requisitos: Python 3.11, PlatformIO e IoT MQTT Panel. Desde la raíz en PowerShell:

```powershell
python -m venv .venv  # Solo si el entorno no existe.
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -B -m iot_shared init
& .\.venv\Scripts\python.exe -B -m iot_shared sync
& .\.venv\Scripts\python.exe -B -m iot_shared check
```

`init` conserva el `.env` existente y su UUID; solo lo crea si falta. `sync`
actualiza `firmware/include/mqtt_config.local.h` y `config/mobile.local.json`,
sin escribir WiFi ni pines. Las copias locales y credenciales no se versionan.

**Firmware:** si falta `firmware/include/device_config.local.h`, copiar la
plantilla indicada abajo y completar WiFi solo localmente. Conservar una copia
existente. Solo el usuario habilita `LED_WIRING_CONFIRMED` tras revisar el
cableado; la plantilla mantiene `false`. Compilar y cargar manualmente,
sustituyendo `COM_ESP32` por el puerto real:

```powershell
$pioSIS234 = "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe"
& $pioSIS234 run -d firmware -e integrated
& $pioSIS234 run -d firmware -e integrated -t upload --upload-port COM_ESP32
```

**Móvil:** abrir IoT MQTT Panel y crear la conexión con los datos de
`config/mobile.local.json` y su `client_id` propio. Añadir un gauge gráfico de
`distance_cm` en cm, tres controles que publiquen los JSON de `commands/leds` y una
vista de confirmaciones en `state/leds`.

**MCP:** instalar las dependencias anteriores y registrar en el cliente de IA
el transporte STDIO con las rutas absolutas a `.venv/Scripts/python.exe` y
`mcp-server/main.py` (argumentos: `-u`, `-B`, ruta del archivo). El cliente inicia
el servidor y su conexión MQTT. La plantilla de Codex indicada abajo está
desactivada: adaptar sus rutas y habilitar la copia personal manualmente según
la [guía MCP](mcp-server/README.md).
El [registro utilizado, sin secretos](docs/auditoria-final.md#registro-mcp-verificado)
se comprobó en lectura durante la auditoría; no se modificó la configuración personal.

## Archivos del entregable y documentación

| Componente | Código y guía | Configuración sin credenciales |
| --- | --- | --- |
| Objeto inteligente | [Firmware integrated](firmware/src/integrated/main.cpp) y [guía de cableado y ejecución](docs/esp32-integrado.md) | [Plantilla del dispositivo](firmware/include/device_config.example.h) y [.env.example](.env.example) |
| Servidor MCP | [Código MCP](mcp-server/iot_mcp/) y [guía MCP](mcp-server/README.md) | [Plantilla de registro en Codex](config/codex.config.toml.example) |
| Panel móvil | IoT MQTT Panel | [Referencia de conexión y controles](config/mobile.config.example.json), no una exportación nativa |

La exportación nativa del panel está pendiente. IoT MQTT Panel documenta esta
función; [exportar y revisar secretos](docs/auditoria-final.md#exportación-móvil-pendiente)
antes de incorporarla al repositorio.

Documentación complementaria: [configuración](docs/configuracion.md),
[contrato MQTT y esquemas](docs/mqtt.md), [arquitectura](docs/arquitectura.md),
[validación y metodología](docs/validacion-final.md), [pruebas sin red](tests/README.md),
[plan de etapas](docs/plan.md), [alternativa de dos placas](docs/dos-esp32.md) y
[auditoría final y publicación](docs/auditoria-final.md). Fuente de requisitos:
[enunciado oficial](Pr%C3%A1ctica_MQTT%20%281%29.md).
