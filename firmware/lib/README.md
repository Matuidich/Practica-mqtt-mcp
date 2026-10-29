# Módulos propios previstos

Aquí se añadirán las clases que encapsulen el estado del dispositivo:

- `DistanceSensor`: medición del HC-SR04 con tiempo máximo de espera.
- `ServoController`: validación y aplicación del ángulo solicitado.
- `MqttConnection`: conexión, reconexión y suscripciones MQTT.
- `DeviceApplication`: coordinación periódica de esos componentes.

Son responsabilidades propuestas; no hay implementaciones ni dependencias
descargadas en esta carpeta. `lib/` contendrá código propio, no copias manuales
de bibliotecas externas.
