# Firmware ESP32 SIS-234

PlatformIO, Arduino, Espressif32 8.0.0 y placa esp32doit-devkit-v1.
El entorno principal y predeterminado es `integrated`, para una sola placa.

| Entorno | Fuente | Función |
| --- | --- | --- |
| integrated | src/integrated/main.cpp | HC-SR04 y los tres LEDs con una sesión MQTT |
| sensor | src/sensor/main.cpp | HC-SR04 conservado: TRIG 5, ECHO 18 con divisor |
| actuator | src/actuator/main.cpp | LEDs rojo 25, amarillo 26, verde 27 |
| hardware-diagnostic | src/diagnostics/main.cpp | Diagnóstico antiguo SG90 GPIO 19 y HC-SR04 |
| esp32dev | src/main.cpp | Esqueleto anterior |

Cada entorno selecciona un único setup/loop. `actuator` depende de PubSubClient
2.8 y Wi-Fi; ya no depende de ESP32Servo. La dependencia ESP32Servo 3.2.1 solo
permanece en hardware-diagnostic. El código SG90 anterior se conserva en
[history/servo/main.cpp](history/servo/main.cpp), fuera de las fuentes activas,
junto con [su guía archivada](../docs/historial/servo.md).

## LEDs

`LedMessages.h` valida command_id y uno a tres booleanos en leds.
`LedController.h` mantiene el estado completo, la última orden y su confirmación
pendiente. `LedSettings.h` obtiene opciones locales con respaldo seguro:
LED_WIRING_CONFIRMED=false y pines 25/26/27. Una copia Wi-Fi antigua no habilita
los LEDs aunque tuviera ACTUATOR_WIRING_CONFIRMED=true para el servo.

Con bandera false no configura GPIO ni confirma órdenes. Habilitado, arranca
con todos apagados y espera un mensaje válido; no hay PWM, rampa ni ciclos
periódicos. Se conserva el estado durante reconexiones y se apaga al reiniciar.
Las escrituras son digitales y secuenciales; applied confirma la consigna lógica.

El [contrato MQTT](../docs/mqtt.md) conserva commands/leds, state/leds y
telemetry/distance. El [cableado y carga de integrated](../docs/esp32-integrado.md)
explica resistencias, polaridad y cómo habilitar la copia local sin sobrescribir
Wi-Fi. La arquitectura anterior de dos placas queda como alternativa histórica.

`integrated` conserva los módulos LED y captura ECHO mediante `AsyncHcsr04`, sin
pulseIn. La tarea MQTT del núcleo 0 usa el MQTT_CLIENT_ID general ya exportado;
loop solo atiende el sensor. Una cola FreeRTOS de longitud uno intercambia la
última medida, sin compartir el cliente MQTT ni acumular lecturas al reconectar.
Las fuentes de sensor/actuator, sus filtros y dependencias siguen intactos.

## Compilar sin conectar placas

Desde la raíz:

```powershell
python -B -m iot_shared sync
python -B -m iot_shared check
python -B -m unittest discover -s tests -v
& "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe" run -d firmware -e integrated
```

Binario principal: .pio/build/integrated/firmware.bin. Para comprobar las
alternativas, añadir `-e sensor -e actuator` al comando de compilación.
No se ha cargado firmware ni abierto un puerto durante esta adaptación.
