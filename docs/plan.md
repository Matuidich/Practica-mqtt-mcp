# Etapas SIS-234

| Etapa | Estado |
| --- | --- |
| Configuración, UUID y contratos compartidos | Preparados y probados sin red |
| Una placa, entorno integrated | Arquitectura definitiva; sensor por interrupciones y MQTT en tarea propia |
| Sensor HC-SR04 | Firmware conservado; el usuario ya comprobó distancia en HiveMQ |
| Actuador de tres LEDs | Funcionamiento comprobado por el usuario con HiveMQ y móvil; firmware conservado |
| Simulador | Modelo LED local listo; transporte MQTT pendiente |
| Aplicación móvil | IoT MQTT Panel comprobado por el usuario; configuración conservada |
| FastMCP/Codex CLI | Servidor y gateway implementados; pruebas offline y STDIO con doble MQTT; registro local habilitado verificado en lectura |
| Integración MCP con ESP32 y broker | Consulta y control por lenguaje natural comprobados físicamente por el grupo; demostración manual sin registro audiovisual guardado |
| Alternativa de dos ESP32 | Etapa anterior conservada; no es la arquitectura definitiva |

El servo se conserva como referencia histórica y el diagnóstico antiguo mantiene
GPIO 19. No se usan sus tópicos para LEDs. La siguiente etapa física sigue la
[guía de una placa](esp32-integrado.md); no se flashea ni publican mensajes automáticamente.
