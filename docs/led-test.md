# Diagnóstico independiente de los tres LEDs

El entorno `led_test` permite comprobar los LEDs con escrituras digitales
directas, sin Wi-Fi, MQTT, HC-SR04 ni configuración local. Su única fuente es
`firmware/src/led_test/main.cpp`. Se selecciona expresamente con `-e led_test`;
`integrated` conserva su código, configuración y selección predeterminada.

## Resultado de la revisión de integrated

- `IntegratedApplication::begin()` usa `led_config::RED_PIN`, `YELLOW_PIN` y
  `GREEN_PIN` tanto en `pinMode(..., OUTPUT)` como al apagar con `LOW`.
- `onMessage()` escribe exactamente esas mismas constantes: bits 1, 2 y 4 del
  estado corresponden a rojo, amarillo y verde. `true` escribe `HIGH`; `false`,
  `LOW`. No hay inversión de lógica ni PWM en este camino.
- `LedSettings.h` toma los pines de `device_config.local.h`, con respaldo
  25/26/27. Durante esta revisión, la copia local ya define 25/26/27 y
  `LED_WIRING_CONFIRMED=true`; no se modificó. La plantilla y el respaldo
  mantienen `false`. Con `false` no se configuran salidas ni se acepta la orden
  para generar una confirmación `applied`.
- TRIG usa GPIO 5 y ECHO GPIO 18. No coinciden con los LEDs; las comprobaciones
  `static_assert` también impiden duplicados entre LEDs y coincidencias con
  TRIG/ECHO. La referencia histórica al servo en GPIO 25 no activa un servo:
  esa fuente no se compila en `integrated`. El diagnóstico SG90 usa GPIO 19
  en otro entorno.
- GPIO 25/26/27 admiten salida digital. Su función alternativa ADC2 tiene
  restricciones con Wi-Fi para **lecturas analógicas**; aquí se usa salida
  digital. No se encontró código activo que reasigne estos tres pines a ADC,
  DAC, PWM u otro periférico.

Referencias oficiales: [GPIO del ESP32](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/gpio.html)
y [pinMode/digitalWrite en Arduino ESP32](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/gpio.html).

`applied` confirma la consigna lógica, no una medición de luz, tensión o
continuidad. Revisar también el objeto `leds` de la confirmación: una orden
válida que deja todos los colores en `false` también devuelve `applied`.
Repetir el mismo `command_id` y contenido puede reenviar una confirmación
anterior sin volver a escribir los GPIO. Esto no demuestra por sí solo una
falla de MQTT ni identifica todavía una causa física.

## Secuencia de led_test

Al arrancar configura GPIO 25/26/27 como `OUTPUT` y los deja en `LOW`.
Después repite indefinidamente:

| Paso | GPIO 25: rojo | GPIO 26: amarillo | GPIO 27: verde | Duración |
| --- | --- | --- | --- | --- |
| 1 | HIGH | LOW | LOW | 2 segundos |
| 2 | LOW | HIGH | LOW | 2 segundos |
| 3 | LOW | LOW | HIGH | 2 segundos |
| 4 | LOW | LOW | LOW | 2 segundos |

Cada paso se anuncia por serie a 115200 baudios. El ciclo completo dura
aproximadamente 8 segundos, más el tiempo de las escrituras y mensajes.
Las pausas `delay(2000)` son apropiadas para esta prueba secuencial sin red.

Este diagnóstico configura sus tres salidas directamente al arrancar y no
consulta `LED_WIRING_CONFIRMED`. No cambia esa bandera en `integrated`.
Antes de cargarlo manualmente, comprobar con la alimentación desconectada:

- Rojo a GPIO 25, amarillo a 26 y verde a 27. Los números son GPIO del ESP32,
  no números de posición física del conector.
- Cada GPIO va por su propia resistencia de 220–330 Ω al ánodo del LED;
  el cátodo va al GND del mismo ESP32. El cátodo suele ser la pata corta y
  el lado plano del encapsulado.
- Verificar GND común, continuidad de cables y posibles cortes en los rieles
  de alimentación de la protoboard. Conectar el cátodo a 3,3 V requeriría
  otra lógica y no corresponde al circuito previsto.

## Compilar sin cargar ni abrir puertos

Desde `M:\IOT\Practica-mqtt-mcp`, en PowerShell:

```powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe" run -d firmware -e led_test
```

Binario: `firmware/.pio/build/led_test/firmware.bin`.

## Carga manual por COM3 y monitor

Los siguientes comandos quedan documentados para que el usuario los ejecute.
La preparación de esta prueba no los ejecuta. Cerrar cualquier monitor que
esté usando COM3 antes de cargar.

```powershell
# Cargar solamente la prueba independiente.
& "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe" run -d firmware -e led_test -t upload --upload-port COM3

# Observar qué GPIO se activa; cerrar con Ctrl+C antes de otra carga.
& "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe" device monitor --port COM3 --baud 115200
```

Se esperan estas cuatro líneas repetidas, separadas por unos 2 segundos:

```text
LED rojo: GPIO 25 HIGH; los otros LOW (2 s).
LED amarillo: GPIO 26 HIGH; los otros LOW (2 s).
LED verde: GPIO 27 HIGH; los otros LOW (2 s).
Todos apagados: GPIO 25, 26 y 27 LOW (2 s).
```

Para volver a `integrated`, cerrar el monitor y ejecutar desde la misma raíz:

```powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe" run -d firmware -e integrated -t upload --upload-port COM3
```

La nueva carga sustituye el programa de la placa. Elegir un entorno en
PlatformIO sin cargarlo no cambia el firmware que está ejecutando el ESP32.
Al volver a `integrated`, este arrancará con todos los LEDs apagados y volverá
a usar la configuración Wi-Fi/MQTT existente y la bandera local de cableado.

## Interpretar la prueba física posterior

Si los tres LEDs siguen la secuencia, el circuito puede encender con estas
salidas; revisar entonces qué firmware está cargado y los valores y
`command_id` de las órdenes y confirmaciones de `integrated`.

Si continúan apagados mientras aparecen los mensajes de `led_test`, MQTT
queda fuera de esta reproducción del fallo. Revisar primero GND común,
polaridad, resistencias, filas de la protoboard y correspondencia de GPIO.
Una comprobación posterior con multímetro entre GPIO y GND debería mostrar
aproximadamente 3,3 V en el paso HIGH y 0 V en LOW. Si el nivel cambia y el
LED no ilumina, orientar la revisión al circuito y al LED. Si no cambia,
revisar el pin identificado, conexiones y posible daño de la salida. Los
mensajes serie tampoco sustituyen una medición eléctrica.

## Verificación realizada sin hardware

- PlatformIO compiló `led_test` e `integrated` con resultado `SUCCESS`.
  El análisis de dependencias de `led_test` indica `No dependencies`:
  no incorpora las bibliotecas Wi-Fi ni PubSubClient del proyecto.
- `python -B -m unittest discover -s tests -v`: 76 pruebas aprobadas, sin
  omisiones. Incluyen las comprobaciones existentes de modos GPIO, niveles
  LED, bloqueo por cableado y confirmaciones de `integrated`, usando dobles
  locales en el PC.
- `python -B -m iot_shared check`: configuración local válida.
- La comparación SHA-256 conservó 101 archivos preexistentes, incluidas las
  fuentes de `integrated`, `.env` y las cabeceras locales. El único archivo
  preexistente modificado es `firmware/platformio.ini`: se añadió al final
  `[env:led_test]`, conservando todos los bytes de sus secciones anteriores.
- No se cargó firmware, abrió un puerto serie, ejecutó un cliente MQTT ni
  realizó una prueba física. La iluminación y los niveles eléctricos quedan
  pendientes de la ejecución manual de `led_test`.
