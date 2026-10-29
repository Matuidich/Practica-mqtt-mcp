# Un ESP32: HC-SR04 y tres LEDs

La arquitectura definitiva utiliza un ESP32 DOIT DevKit V1 con el entorno
`integrated`. Los periféricos ya están montados según informó el usuario, pero
el firmware mantiene `LED_WIRING_CONFIRMED=false` hasta que el usuario confirme
físicamente los cables. Los entornos `sensor`, `actuator`, `esp32dev` y
`hardware-diagnostic` se conservan para referencia y usos separados.

## Conexiones en la misma placa

| Componente | Señal | Conexión |
| --- | --- | --- |
| HC-SR04 | TRIG | GPIO 5 |
| HC-SR04 | ECHO | GPIO 18 mediante divisor de tensión; no conectar ECHO de 5 V directamente |
| LED rojo | Ánodo | GPIO 25 → resistencia propia de 220–330 Ω → ánodo; cátodo a GND |
| LED amarillo | Ánodo | GPIO 26 → resistencia propia de 220–330 Ω → ánodo; cátodo a GND |
| LED verde | Ánodo | GPIO 27 → resistencia propia de 220–330 Ω → ánodo; cátodo a GND |

El HC-SR04 conserva su alimentación y divisor actuales. Todas las masas van al
GND de este ESP32. Revisar la polaridad de cada LED, el divisor y la ausencia de
cortocircuitos con la alimentación desconectada. No conectar un servo a estos GPIO.

## Contratos y configuración intactos

Se reutilizan `.env`, UUID, Wi-Fi y cabecera generada existentes. No es necesario
modificarlos ni ejecutar sync por este nuevo entorno. Los tres tópicos siguen
siendo los derivados del mismo prefijo:

- `telemetry/distance`: distancia positiva, device_id y uptime_ms.
- `commands/leds`: command_id y cambios booleanos en leds.
- `state/leds`: command_id, estado completo, device_id, uptime_ms y applied.

Ver el [contrato y ejemplos JSON](mqtt.md). Los validadores, los duplicados y
la política de confirmación pendiente se reutilizan sin modificar sus esquemas.
applied confirma la asignación de GPIO; no mide luz ni verifica el circuito.

La única sesión MQTT usa `MQTT_CLIENT_ID`, correspondiente al rol FIRMWARE y
sufijo `-esp32`, que ya existía y es distinto de sensor/actuator. No se crean
nuevas claves ni identidades. Se conservan los device_id lógicos anteriores:
SENSOR_DEVICE_ID en distancia y ACTUATOR_DEVICE_ID en confirmaciones LED, aunque
ambos procedan ahora de la misma placa. No ejecutar simultáneamente otro cliente
que utilice ese mismo MQTT_CLIENT_ID.

LED_WIRING_CONFIRMED sigue false por defecto, incluida una copia local antigua
que no defina esa macro. Con false no se configuran ni escriben los GPIO LED y
se rechazan órdenes sin applied; la medición y publicación de distancia funcionan.
Su estado lógico arranca apagado. Con true se configuran los tres GPIO en LOW
y solo cambian con una orden válida. Un GPIO bloqueado permanece como entrada,
por lo que no sustituye una revisión eléctrica del montaje.

## Medición y MQTT sin esperas largas en loop

`AsyncHcsr04` captura los flancos de ECHO mediante una interrupción con secciones
críticas cortas. loop inicia un pulso TRIG breve (2 µs LOW y 10 µs HIGH), consulta
el resultado y cede 1 ms. No usa pulseIn ni espera el eco con un bucle. Mantiene
timeout local (30 ms por defecto), intervalo de publicación existente y rango
de 2–400 cm; los ecos inválidos se descartan sin publicar un cero. Las restas
sin signo contemplan los desbordamientos de micros y millis.

PubSubClient y Wi-Fi siguen usando sus límites y reconexión progresiva actuales.
Sus operaciones síncronas pueden tardar durante conexión, DNS o pérdida de red;
se ejecutan en una tarea FreeRTOS del núcleo 0, con 8192 bytes de pila y una
pausa de un tick en cada vuelta. Esa tarea es la única que usa el cliente MQTT,
procesa callbacks, escribe las órdenes LED y publica confirmaciones. loop no
espera esas operaciones y puede continuar midiendo.

Una cola FreeRTOS de longitud uno comunica la lectura más reciente. Se sustituye
una lectura pendiente por otra nueva, se descartan muestras caducadas y se limpia
la cola al desconectar o reconectar. No hay ráfagas de medidas antiguas al volver
la red. Una confirmación LED pendiente conserva su estado y reintentos, sin
impedir el envío de distancias. Si falla crear la cola o tarea, no se inicia
MQTT y los LEDs quedan apagados.

La cola y las secciones críticas protegen los datos entre tareas e interrupción;
no se comparte PubSubClient entre núcleos. Referencia de las APIs usadas:
[FreeRTOS de ESP-IDF](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/system/freertos_idf.html).
Las pruebas del PC comprueban intercalados deterministas, no latencia real ni
exactitud física bajo carga Wi-Fi; esa validación queda pendiente con la placa.

## Compilar y probar sin hardware

Desde la raíz del proyecto en PowerShell:

```powershell
$pioSIS234 = "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe"
& $pioSIS234 run -d firmware -e integrated
python -B -m unittest discover -s tests -v
python -B -m iot_shared check
```

`integrated` es el entorno predeterminado. Su filtro compila únicamente
src/integrated/main.cpp, con un solo setup/loop. El binario está en
firmware/.pio/build/integrated/firmware.bin. Los entornos anteriores conservan
sus filtros y dependencias; también se puede comprobar su compilación usando
`run -d firmware -e sensor -e actuator`.

## Carga y monitor: ejecutar solo manualmente

Antes de habilitar salidas, revisar físicamente el montaje con las fuentes
apagadas. Después el usuario puede añadir o editar solo las opciones LED en su
device_config.local.h, sin reemplazar las credenciales:

```cpp
#define LED_WIRING_CONFIRMED true
#define LED_RED_PIN 25
#define LED_YELLOW_PIN 26
#define LED_GREEN_PIN 27
```

Esta entrega conserva la bandera false. Con ella se puede cargar y comprobar
distancias, pero las órdenes LED se rechazarán hasta confirmar, habilitar y
recompilar. Evitar emisores automáticos y órdenes retenidas durante la revisión.

Desde la raíz, sustituir COM_ESP32 por el puerto real comprobado de la placa:

```powershell
$pioSIS234 = "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe"
$puertoESP32 = "COM_ESP32"
& $pioSIS234 run -d firmware -e integrated -t upload --upload-port $puertoESP32
& $pioSIS234 device monitor --port $puertoESP32 --baud 115200
```

El monitor puede reiniciar el ESP32 al abrirse; Ctrl+C lo cierra. Se esperan el
mensaje `ESP32 integrated: HC-SR04 y LEDs rojo, amarillo y verde.`, el bloqueo de
salidas mientras la bandera sea false y lecturas `HC-SR04 ... cm`, incluso sin
conexión MQTT. También se muestran los mensajes de conexión y las distancias
enviadas o descartadas. `enviado a TCP` no garantiza entrega MQTT QoS 0. Con
cableado habilitado y una orden manual posterior, observar la confirmación LED
con el mismo command_id desde el consumidor MQTT. Los comandos serie s/x del
diagnóstico antiguo no controlan integrated.

No se han ejecutado carga, monitor, publicaciones reales ni pruebas de hardware
durante esta adaptación.

## Resultado de la verificación local

- PlatformIO: integrated, sensor y actuator compilaron con SUCCESS.
- Binario integrated final: RAM estática 47 800 bytes (14.6%) y flash
  969 296 bytes (74.0%). La tarea y cola también necesitan memoria dinámica.
- Suite Python/C++ completa: 76 pruebas aprobadas, sin omisiones; diez nuevas
  cubren integrated y conservan las regresiones anteriores.
- iot_shared check: configuración local válida; no se ejecutó sync.
- SHA-256 confirma que `.env`, Wi-Fi local, plantilla, cabecera y referencia
  móvil derivadas, fuentes de sensor/actuator y módulos compartidos LED/red
  permanecen intactos. PlatformIO solo añade integrated y cambia el entorno
  predeterminado; los bloques anteriores conservan sus filtros y dependencias.
- Siguen pendientes las mediciones de latencia, corriente, iluminación y
  funcionamiento conjunto en la placa real, mediante ejecución manual.
