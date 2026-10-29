# Contrato MQTT compartido

## Transporte e identidades

Broker configurado: `broker.hivemq.com:1883`, MQTT 3.1.1 sobre TCP. Se conserva
el UUID y prefijo de `.env`. Cada rol tiene su propio client_id derivado del UUID:
`sensor`, `actuator`, `mcp`, `simulator`, `mobile` y `firmware` general. El entorno
integrated usa una sesión con el rol firmware; sensor/actuator son alternativas.
Para
varias instancias simultáneas del mismo rol se necesitarán sufijos adicionales;
no iniciar dos clientes con el mismo identificador.

| Tópico relativo al prefijo | Publica | Recibe | QoS | Retain |
| --- | --- | --- | --- | --- |
| `telemetry/distance` | Integrated, sensor o simulador | Móvil y MCP | 0 | false |
| `commands/leds` | Móvil o MCP | Integrated, actuador LED o simulador | 0 | false |
| `state/leds` | Integrated, actuador LED o simulador | Móvil y MCP | 0 | false |

`commands/servo` y `state/servo` siguen reservados a los esquemas históricos
SG90. No se renombran ni se reutilizan con otro significado. El actuador activo
y el simulador LED no se suscriben ni aplican órdenes de servo. Los modelos
Python anteriores se conservan para compatibilidad y pruebas históricas.

## Reglas estrictas

- UTF-8 y como máximo 1024 bytes, incluyendo espacios.
- Objeto JSON con exactamente los campos del esquema. Sin claves repetidas,
  campos desconocidos, datos sobrantes, NaN o Infinity.
- command_id y device_id: 1–64 caracteres ASCII; primero letra o número;
  los siguientes pueden incluir punto, guion y guion bajo.
- uptime_ms: entero de 0 a 4294967295, sin booleanos ni decimales; tiempo desde
  arranque y no fecha UTC. Puede desbordarse o volver a cero después de reiniciar.
- Los valores LED son booleanos `true`/`false`, nunca 0/1, texto o null.

Los modelos y transformaciones Python están en `iot_shared.messages` y
`iot_shared.leds`; simulador y herramientas MCP los reutilizan. El firmware C++
se compara con esos validadores mediante pruebas cruzadas. Los esquemas formales
están en [led-command.schema.json](schemas/led-command.schema.json) y
[led-state.schema.json](schemas/led-state.schema.json). Los esquemas describen
la estructura; los validadores comprueban además el límite de bytes, las claves
repetidas y los enteros sin decimales ni exponentes.

## Distancia conservada

```json
{"distance_cm":42.5,"device_id":"sensor-01","uptime_ms":12345}
```

`distance_cm` debe ser finito y mayor que cero; no admite booleanos. El firmware
sensor mantiene sus pines, intervalo, timeout y descarte de ecos inválidos. Su
contrato, prefijo y tópico no cambian.

## Órdenes LED

```json
{"command_id":"led-red-001","leds":{"red":true}}
```

`leds` contiene entre uno y tres colores: `red`, `yellow`, `green`. Los omitidos
conservan su estado. La orden establece valores absolutos: no hay toggle ni ciclos
automáticos. Los tres pueden estar encendidos a la vez.

Encender solo rojo y apagar los demás:

```json
{"command_id":"led-only-red-001","leds":{"red":true,"yellow":false,"green":false}}
```

Encender solo amarillo:

```json
{"command_id":"led-only-yellow-001","leds":{"red":false,"yellow":true,"green":false}}
```

Encender solo verde:

```json
{"command_id":"led-only-green-001","leds":{"red":false,"yellow":false,"green":true}}
```

Apagar rojo sin modificar los otros:

```json
{"command_id":"led-red-off-001","leds":{"red":false}}
```

Apagar todos:

```json
{"command_id":"led-all-off-001","leds":{"red":false,"yellow":false,"green":false}}
```

Asignar un command_id nuevo por orden. Móvil/MCP deben guardar ese ID hasta
recibir confirmación o agotar su espera. Una frase como «enciende el rojo y apaga
los demás» se prepara con `only_led("red", command_id)`, sin ampliar el protocolo.

## Confirmación

```json
{"leds":{"red":true,"yellow":false,"green":false},"command_id":"led-only-red-001","device_id":"actuator-01","uptime_ms":12345,"status":"applied"}
```

Incluye siempre los tres colores y el mismo command_id. `applied` significa
que el firmware asignó los niveles GPIO; no mide luz ni comprueba el cableado.
El simulador confirma el estado en memoria. Con cableado sin confirmar el
firmware rechaza órdenes y no publica un applied falso. No se publica un estado
de arranque sin command_id: hasta la primera confirmación, la interfaz mostrará
estado desconocido, sin asumir que conserva el de una sesión anterior.

En el firmware hay una sola confirmación pendiente. Una orden nueva mientras está pendiente se
rechaza como ocupada, sin cola. Repetir la última con el mismo contenido no
vuelve a escribir GPIO; tras enviarse su confirmación se permite reenviarla con
el uptime original. Reutilizar ese último ID con cambios distintos se rechaza.
La comparación ignora el orden de las claves, pero distingue cambios omitidos
de cambios explícitos. Solo se recuerda la última orden, no un historial
ilimitado ni persistente: usar siempre IDs únicos.

En desconexión se conservan los niveles lógicos y la confirmación pendiente;
al reconectar se restaura la suscripción y se reintenta con espera progresiva
limitada. Un reinicio deja los LEDs apagados y pierde la deduplicación anterior.
QoS 0 puede perder órdenes y confirmaciones. Publicar con éxito no demuestra
que se recibió ni permite a MCP declarar applied por su cuenta.

## Comportamiento del puente MCP

El servidor conserva estos tópicos y esquemas. Se suscribe a distancia y estado;
no usa los tópicos históricos del servo. Para confirmar una orden comprueba el
JSON completo de `state/leds`, el mismo ID y cada valor solicitado. Los otros
colores se observan como estado, sin asumir su valor anterior.

MCP también admite una sola orden pendiente, sin cola. Guarda los últimos 128
resultados durante la ejecución: igual ID y contenido comparten la espera o
devuelven el resultado guardado; un contenido distinto da `conflicting_id`.
Este historial de MCP es independiente de la memoria de la última orden del
firmware y no ofrece deduplicación persistente después de un reinicio.

La espera es de 5 s por defecto, configurable por llamada entre más de 0 y 30 s.
Un timeout o desconexión no demuestra que la orden haya fallado físicamente;
no se republica automáticamente. La reconexión restaura las suscripciones con
espera progresiva limitada. Los mensajes retained, inválidos y confirmaciones
tardías o duplicadas de llamadas terminadas no se toman como confirmaciones
actuales. Un estado de otro ID, por ejemplo del móvil, puede observarse pero no
resuelve la espera de una orden diferente. Ver [herramientas MCP](../mcp-server/README.md).
