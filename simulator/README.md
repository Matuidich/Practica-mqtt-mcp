# Simulador preparado, sin transporte de red

`iot_simulator.device.SimulatedDevice` modela los tres LEDs en memoria mediante
LedDevice y los validadores de iot_shared. Inicia apagado; acepta solo el tópico
LED de su prefijo, devuelve LedState completo y conserva la confirmación pendiente
hasta confirmation_sent(). Permite producir DistanceReading sin alterar su
contrato. No simula un servo ni controla hardware.

Ya se prueba localmente con las funciones preparatorias MCP. Aún faltan cliente
Paho MQTT, inicio/cierre explícitos, bucle de distancias, reconexión y envío real
de confirmaciones. El punto main.py permanece inerte y escribe por stderr; no
lo ejecutar como cliente contra HiveMQ en esta etapa.

La configuración se carga con Settings desde el .env existente y el client_id
SIMULATOR es distinto del firmware. El [contrato](../docs/mqtt.md) es compartido;
no duplicar validaciones en este paquete.
