# Servidor MCP para distancia y tres LEDs

FastMCP 4.1.3 expone herramientas por STDIO. Paho MQTT 2.1.0 conecta el puente
con el contrato existente del ESP32 `integrated` y de IoT MQTT Panel.
Importar módulos y construir el servidor no inicia conexiones. Su ciclo de vida
inicia MQTT al arrancar y lo cierra al terminar. El diagnóstico va a `stderr`;
`stdout` se reserva al protocolo MCP.

## Herramientas

| Nombre | Propósito | Ejemplo de argumentos MCP |
| --- | --- | --- |
| `get_last_distance` | Última distancia, edad, fecha de recepción y vigencia | `{}` |
| `get_led_state` | Último `state/leds` observado, también de órdenes móviles | `{}` |
| `set_led` | Cambia un LED y conserva los otros dos | `{"color":"red","on":true}` |
| `set_leds` | Cambia uno, dos o tres colores en una publicación | `{"changes":{"red":true,"yellow":false,"green":true}}` |
| `set_only_led` | Enciende un color y apaga los demás | `{"color":"green"}` |
| `turn_off_all_leds` | Apaga los tres | `{}` |

`set_led` admite `on:false` para apagar individualmente. Los colores son
`red`, `yellow`, `green` y los valores son booleanos JSON estrictos. Las órdenes
no admiten toggle ni crean automatismos a partir de la distancia.

Las cuatro herramientas que escriben admiten `command_id` opcional y `timeout_s`
(por defecto 5, mayor que 0 y como máximo 30 segundos). Al omitir el ID se genera
un UUID v4 para esa orden. Las funciones `prepare_*` anteriores se conservan y
reutilizan los validadores de `iot_shared`, igual que las herramientas reales.
No hay herramientas del antiguo servomotor.

## Confirmaciones, caché y fallos

`mqtt_accepted:true` indica que Paho aceptó localmente la publicación QoS 0,
sin retain. No demuestra que el broker o ESP32 la recibieron. Para devolver
`status:applied` y `confirmation_verified:true`, el servidor exige un JSON válido
de `state/leds`, con el mismo `command_id`, los tres estados booleanos y todos los
colores solicitados coincidentes. `confirmation` contiene el mensaje recibido.
`applied` informa niveles GPIO lógicos, no luz medida ni cableado comprobado.

Los resultados posibles de una orden son:

- `applied`: confirmación correlacionada y valores verificados.
- `timeout`: venció la espera. La orden podría haberse aplicado; no se reenvía.
- `disconnected`: conexión no disponible, perdida durante la espera o servidor cerrado.
- `publish_failed`: Paho rechazó la publicación o falló su envío.
- `confirmation_mismatch`: mismo ID, pero valores diferentes de los solicitados.
- `busy`: otra orden está pendiente; no se encola la nueva.
- `conflicting_id`: se intentó reutilizar un ID con contenido diferente.

Repetir una llamada con igual ID y contenido comparte la espera original o
devuelve su resultado guardado, sin republicar. El historial se limita a las
últimas 128 órdenes aceptadas y no persiste después de reiniciar. Los IDs
expulsados del historial ya no tienen esa protección: usar IDs nuevos para cada
orden nueva. Una confirmación duplicada o tardía de una llamada terminada no
reemplaza una observación más reciente ni cambia retroactivamente el resultado.

Los mensajes ajenos al prefijo, inválidos o retained se ignoran. Los estados
válidos de órdenes del móvil se muestran como observaciones, sin confirmar por
ello una orden pendiente de MCP con otro ID.

`get_last_distance` devuelve `unknown` hasta recibir la primera lectura,
`fresh` para una lectura vigente y `stale` cuando supera
`DISTANCE_STALE_AFTER_S` o se perdió su conexión. Incluye `age_s`, `received_at`
y `current_connection` si existe una lectura. El tiempo de vigencia se calcula
con reloj monotónico; `uptime_ms` se conserva como dato del dispositivo.
El contrato no usa retain: al iniciar hay que recibir una publicación nueva.

`get_led_state` devuelve `unknown`, `observed` o `stale`. A diferencia del sensor,
los LEDs no publican periódicamente; se informa su edad y la desconexión invalida
su vigencia. Una reconexión no convierte automáticamente la caché anterior en
actual. MQTT no modifica los niveles del dispositivo al desconectarse.

Paho gestiona la reconexión con espera exponencial entre el mínimo y máximo del
`.env`. Cada conexión restaura ambas suscripciones; el gateway permite publicar
después de recibir sus dos confirmaciones SUBACK. No almacena órdenes para
reproducirlas al reconectar ni reintenta automáticamente una orden incierta.
El servidor MCP puede iniciar y responder aunque MQTT no esté disponible.

## Verificación local sin HiveMQ

Desde la raíz, usando las dependencias ya instaladas en `.venv`:

```powershell
& .\.venv\Scripts\python.exe -B .\mcp-server\main.py --check-offline
& .\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
& .\.venv\Scripts\python.exe -B -m iot_shared check
```

`--check-offline` ejecuta `iot_mcp/offline_check.py`: inicia FastMCP en memoria,
enumera y llama las seis herramientas, usa un cliente MQTT falso y comprueba el
cierre. Bloquea conexiones y DNS y usa la plantilla con un UUID ficticio.
No lee ni modifica el `.env` real.

`tests/test_mcp_server.py` comprueba además el protocolo STDIO real en un proceso
separado mediante `tests/stdio_mcp_harness.py`. Se conserva la entrada real y se
sustituye MQTT por el doble; se impide construir un cliente Paho real. Verifica
`initialize`, `tools/list`, lectura y orden con confirmación simulada. Cada línea
de `stdout` debe ser JSON-RPC; un diagnóstico de prueba debe estar en `stderr`.
La prueba arranca desde otra carpeta para comprobar las rutas.

Las pruebas del gateway cubren cambios parciales, todas las combinaciones,
timeout, desconexión, resuscripción, llamadas concurrentes y duplicadas, errores
de confirmación y mensajes retained. Las pruebas MCP se omiten explícitamente
si FastMCP no está instalado; en `.venv` deben ejecutarse todas.

## Registro manual en Codex CLI para Windows

El siguiente comando queda documentado para que lo ejecutes cuando corresponda;
no se ha modificado la configuración personal de Codex:

```powershell
codex mcp add sis234-iot -- "M:\IOT\Practica-mqtt-mcp\.venv\Scripts\python.exe" -u -B "M:\IOT\Practica-mqtt-mcp\mcp-server\main.py"
codex mcp list
```

La sintaxis se comprobó con `codex mcp add --help` y la
[documentación oficial de OpenAI](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
El intérprete absoluto usa `.venv` sin requerir `Activate.ps1`.
`main.py` encuentra el `.env` de la raíz aunque Codex tenga otro directorio de
trabajo. Se puede pasar `--env-file` con otra ruta explícita. No hay sobrescrituras
implícitas de MQTT desde variables del proceso ni cambios de prefijo o client_id.
Al arrancar normalmente desde Codex, el servidor sí iniciará su conexión MQTT;
no envía órdenes LED de arranque. Las escrituras ocurren al llamar herramientas.

Falta realizar, con autorización separada, la conexión real MCP → HiveMQ →
ESP32 y verificar las confirmaciones junto con IoT MQTT Panel. Las comprobaciones
locales no certifican el enlace ni la respuesta del hardware.
