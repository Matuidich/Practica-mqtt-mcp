# Migración del actuador SG90 a tres LEDs

Esta página documenta la migración anterior. La arquitectura definitiva de una
placa y su verificación adicional están en [ESP32 integrado](esp32-integrado.md).

El actuador activo aplica cambios digitales independientes en GPIO 25/26/27.
El sensor conserva su implementación, pines y tópico de distancia. El UUID,
el prefijo y Wi-Fi locales se conservan; `sync` añade tópicos LED solo a los
dos archivos derivados. No se habilita hardware ni se inicia un cliente real.

## Archivos de implementación

| Archivos | Cambio |
| --- | --- |
| firmware/src/actuator/main.cpp | Sustituye Servo/PWM por salidas LED validadas y confirmación completa |
| firmware/platformio.ini | Retira ESP32Servo del entorno actuator; conserva diagnóstico |
| firmware/include/device_config.example.h | Añade opciones LED bloqueadas por defecto |
| firmware/include/distributed/LedSettings.h | Opciones locales con respaldo false y validación de pines distintos |
| firmware/include/distributed/LedMessages.h | Parser LED estricto y codificación del estado completo |
| firmware/include/distributed/LedController.h | Estado, cambios parciales, deduplicación y confirmación pendiente |
| firmware/include/distributed/WireMessages.h | Extrae lector JSON común sin cambiar el mensaje de distancia ni el contrato servo |
| firmware/include/distributed/WifiMqttConnection.h | Ajusta rutas de include para probar la implementación real con dobles; conserva comportamiento de red |
| iot_shared/topics.py, messages.py, leds.py | Tópicos, modelos LED y transformaciones compartidas |
| iot_shared/config.py | Identifica los límites servo como compatibilidad histórica |
| iot_shared/local_config.py, __main__.py | Exporta/publica en show los tópicos LED y sustituye controles móviles por interruptores |
| config/mobile.config.example.json | Referencia móvil con gauge y controles LED |
| simulator/iot_simulator/device.py | Modelo de dispositivo LED en memoria, sin transporte MQTT |
| mcp-server/iot_mcp/tools.py, mqtt_gateway.py | Preparación pura e interfaz del futuro gateway LED |
| firmware/history/servo/main.cpp, README.md | Conserva el actuador SG90 anterior fuera de las fuentes activas |

## Pruebas y documentación

- Nuevos `tests/test_leds.py` y `tests/test_led_firmware.py`.
- Nuevos `firmware/test/leds/test_led_actuator.cpp`, `test_connection.cpp` y
  los cinco dobles de Arduino, Wi-Fi, PubSubClient, configuración y transporte.
- `tests/test_configuration.py` verifica exportación LED y conservación de Wi-Fi
  y opciones LED en archivos temporales.
- `firmware/test/actuator/test_actuator.cpp` apunta al servo archivado;
  `tests/test_actuator_application.py` identifica esas regresiones históricas.
- Nuevos esquemas `docs/schemas/led-command.schema.json` y
  `docs/schemas/led-state.schema.json`.
- `AGENTS.md`, README raíz, README de firmware/pruebas/simulador/MCP y guías
  `docs/mqtt.md`, `dos-esp32.md`, `arquitectura.md`, `configuracion.md` y `plan.md`
  reflejan la nueva etapa. `docs/historial/servo.md` conserva la guía anterior.

Archivos locales derivados actualizados por `sync` y excluidos de Git:
`firmware/include/mqtt_config.local.h` y `config/mobile.local.json`.
`.gitignore` ya los protegía y no necesita modificarse. No se sobrescribe la
copia Wi-Fi `device_config.local.h`; una copia antigua queda bloqueada para LEDs.

## Verificación

- `python -B -m unittest discover -s tests -v`: 66 pruebas aprobadas, sin omisiones.
  Incluye regresiones históricas y 15 casos nuevos LED; algunos recorren múltiples
  escenarios C++ y combinaciones JSON dentro del mismo caso.
- PlatformIO `sensor`: SUCCESS; RAM 47 168 bytes, flash 960 140 bytes.
- PlatformIO `actuator`: SUCCESS; RAM 47 264 bytes, flash 959 172 bytes.
- La compilación actuator solo enlaza PubSubClient y Wi-Fi como bibliotecas de
  aplicación; ESP32Servo permanece exclusivamente en hardware-diagnostic.
- `python -B -m iot_shared check`: configuración derivada válida.

Las integraciones ejecutadas usan dobles sin sockets, puertos ni GPIO reales.
No se ha cargado firmware, conectado a HiveMQ ni hecho commits o push.
La iluminación real y el cliente MQTT del simulador siguen pendientes; también
la app móvil, composición FastMCP y confirmación del docente sobre dos placas.
