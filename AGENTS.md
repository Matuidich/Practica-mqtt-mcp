# Instrucciones de trabajo para SIS-234

## Alcance actual

- Está autorizado preparar el entorno `integrated` para un solo ESP32 DOIT
  DevKit V1: publica HC-SR04 y recibe órdenes para tres LEDs con una sesión MQTT.
  El usuario eligió definitivamente una placa. `sensor` y `actuator` separados
  se conservan como alternativas, y el SG90 solo como referencia histórica.
  Se permite instalar dependencias, compilar y ejecutar pruebas sin red.
  No ejecutar clientes contra el broker, cargar firmware o abrir puertos serie.
  Simulador y herramientas MCP funcionales siguen pendientes.
- Explicar en español los conceptos y el propósito de cada cambio; el usuario
  está aprendiendo MQTT y MCP desde cero.
- No conectar al broker, publicar mensajes, ejecutar comandos sobre hardware,
  flashear firmware ni abrir el monitor serie. Los comandos de carga y monitor
  solo se documentan para que el usuario los ejecute manualmente.
- No crear commits ni hacer push en esta etapa.
- No activar servidores MCP ni modificar la configuración personal de Codex.

## Arquitectura y configuración

- `firmware/`: PlatformIO y Arduino, placa confirmada `esp32doit-devkit-v1`.
  Entorno principal y predeterminado `integrated`, con fuentes independientes
  de los entornos anteriores `sensor` y `actuator`, que deben conservarse.
  Conservar el esqueleto `esp32dev` y el diagnóstico `hardware-diagnostic`.
- El diagnóstico usa señal SG90 en GPIO 19, TRIG en GPIO 5 y ECHO en GPIO 18
  mediante divisor. Espera `s` por serie, hace un único ciclo limitado con
  pausas y permite `x` para desactivar PWM; no repetir movimientos en bucle.
- El actuador LED usa rojo GPIO 25, amarillo 26 y verde 27, cada uno con su
  resistencia de 220–330 ohmios hacia el ánodo y cátodo a GND. Conservar
  `LED_WIRING_CONFIRMED=false`: sin confirmar no configurar salidas ni aplicar
  órdenes. Solo el usuario verifica y habilita su copia local. El arranque
  habilitado deja los tres apagados. El diagnóstico antiguo conserva GPIO 19.
- `firmware/history/servo/main.cpp` conserva el actuador SG90, fuera de src y
  de los entornos activos. Sus pruebas históricas se mantienen por separado.
- La propuesta anterior de dos ESP32 queda como referencia; su aceptación
  académica pendiente no condiciona la arquitectura actual de una placa.
- `integrated` usa TRIG 5 y ECHO 18 con divisor, y LEDs 25/26/27. Capturar ECHO
  por interrupciones, sin pulseIn en el bucle principal. Una tarea FreeRTOS es
  la única propietaria del cliente MQTT y sus callbacks; intercambiar distancias
  mediante una cola acotada, sin reproducir lecturas antiguas al reconectar.
- Reutilizar MQTT_CLIENT_ID / rol FIRMWARE para integrated. Los identificadores
  sensor/actuator anteriores y todos los tópicos/contratos permanecen iguales.
- `mcp-server/`: Python y el paquete independiente `fastmcp`.
- `simulator/`: cliente MQTT que representará al ESP32 sin hardware.
- HiveMQ público: `broker.hivemq.com:1883`, MQTT sobre TCP.
- Prefijo único y configurable, compartido entre los componentes. Cada cliente
  debe tener un identificador MQTT distinto.
- Mantener el contrato de tópicos y mensajes en `docs/mqtt.md`.
- No modificar el `.env` existente, su UUID ni el tópico/esquema de distancia.
  Los nuevos tópicos son `commands/leds` y `state/leds`, bajo el mismo prefijo.
  No reutilizar los tópicos servo con otro significado. Conservar los roles
  e identificadores anteriores y exportar con `sync`.
- Credenciales y pines nuevos en `device_config.local.h`, ignorado por Git.
  Sin esa copia se compila con la plantilla de SSID vacío y movimiento bloqueado.
- `iot_shared/` contiene la implementación común: no duplicar validadores o
  ajustes en MCP y simulador. `.env` es la fuente local, sin sobrescrituras
  implícitas desde el entorno del proceso.
- Generar UUID v4 solo al crear `.env`. `init` conserva archivos existentes;
  `sync` actualiza exclusivamente los dos archivos derivados, sin tocar Wi-Fi
  ni pines. Tras cambiar `.env`, ejecutar `sync` y `check`.
- Derivar `telemetry/distance`, `commands/leds` y `state/leds` del mismo prefijo.
  Los tópicos y claves de configuración servo quedan como compatibilidad
  histórica. `command_id` relaciona una orden con su confirmación `applied`.
  Las órdenes LED permiten cambios parciales booleanos; las confirmaciones
  incluyen siempre red, yellow y green. Omitir un color conserva su estado.
- Nunca añadir credenciales, archivos `.env`, configuración Wi-Fi real ni claves
  privadas. Usar los archivos de ejemplo y sus copias locales ignoradas por Git.

## Criterios para las siguientes etapas

- Separar configuración, transporte MQTT, estado del dispositivo y herramientas
  MCP. Usar clases para componentes con estado y funciones para transformaciones.
- No abrir conexiones al importar módulos. Iniciar y cerrar recursos de forma
  explícita; los mensajes de diagnóstico MCP deben ir a stderr, no a stdout.
- Implementar reconexión con espera progresiva limitada y restaurar las
  suscripciones después de cada conexión. No usar bucles de reintento sin pausa.
- Validar mensajes y rangos antes de actuar. No confundir una publicación MQTT
  aceptada con una confirmación física: applied informa niveles GPIO lógicos,
  no luz medida ni cableado comprobado.
- Las pruebas por defecto deben ser locales y sin red. Las futuras pruebas de
  integración y hardware tendrán una ejecución separada y explícita.
- Actualizar documentación y pruebas pertinentes al cambiar comportamiento.

## Verificación de esta etapa, desde la raíz

```powershell
python -B -m unittest discover -s tests -v
python -B -m iot_shared check
```

La configuración usa la biblioteca estándar de Python 3.11. Las pruebas cruzadas
de firmware usan G++ si está disponible y no acceden a hardware. Los puntos de
entrada Python MQTT/MCP siguen inertes. Al implementar un arranque real
en otra etapa, adaptar sus pruebas a dobles del transporte; no mantener una
expectativa de arranque fallido si deja de aplicar.
