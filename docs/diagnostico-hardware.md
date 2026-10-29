# Diagnóstico local: DOIT ESP32 DevKit V1, HC-SR04 y SG90

El proyecto ahora también tiene los entornos distribuidos `sensor` y `actuator`.
Este diagnóstico se conserva sin modificar su código o pines: su servo sigue
en GPIO 19. La sección de restauración de esta guía se refiere al esqueleto
anterior `esp32dev`; para la arquitectura actual consultar [la guía de ESP32 integrado](esp32-integrado.md).

Este firmware es una prueba independiente de la aplicación IoT. No inicia
Wi-Fi, MQTT o MCP, no lee `.env` y no utiliza la cabecera MQTT generada.
No se carga ni abre el puerto serie al compilar.

## Montaje utilizado

| Componente | Conexión declarada |
| --- | --- |
| SG90 | Señal GPIO 19, alimentación 5 V y GND común |
| HC-SR04 | TRIG GPIO 5 y ECHO GPIO 18 mediante divisor de tensión |
| Monitor Serie | 115200 baudios |

Se conserva el divisor ya instalado en ECHO y la masa común. Los pines y los
tiempos de esta prueba están en `firmware/include/diagnostics/DiagnosticConfig.h`;
no modifican los pines pendientes de la aplicación principal.

## Qué hace el programa

El sensor mide cada 500 ms. Envía un pulso TRIG de 10 microsegundos y mide la
duración del retorno ECHO. La distancia aproximada en centímetros es ese tiempo
en microsegundos dividido por 58: el sonido recorre el trayecto de ida y vuelta.
Si no llega eco dentro de 30 ms, muestra una lectura inválida en lugar de una
distancia cero. También identifica resultados fuera del rango nominal 2–400 cm.
Los tiempos y la conversión siguen la [hoja de datos del HC-SR04](https://cdn.sparkfun.com/datasheets/Sensors/Proximity/HCSR04.pdf).

El servo permanece sin PWM hasta recibir `s` por serie. Entonces recibe una
consigna inicial de 90°, espera 1500 ms y realiza **una sola secuencia**:

```text
90° → 45° → 90° → 135° → 90° → fin y PWM desactivado
```

Después del centrado inicial, avanza un grado por actualización, con un intervalo
mínimo de 25 ms y una pausa de 1500 ms en cada objetivo, incluido el último.
La secuencia dura unos 12 segundos y no se repite automáticamente. Para una
nueva prueba hace falta reiniciar y volver a enviar `s`.

`x` cancela la secuencia y desactiva PWM, también durante las pausas. `h` o `?`
muestra la ayuda. Un monitor que envíe salto de línea junto a la letra también
funciona. Tras finalizar o cancelar, el sensor sigue informando distancias.
Al desactivar PWM el servo deja de recibir una consigna de mantenimiento.

El SG90 no informa su posición real. Por eso el centrado inicial a 90° puede
moverlo desde una posición desconocida; el programa no puede interpolar ese
primer movimiento sin realimentación. Los ángulos mostrados son consignas,
no mediciones físicas. Se usa PWM de 50 Hz y una ventana de 1000–2000 µs para
el mapeo 0–180°; esta prueba manda únicamente 45–135°, dentro de esa ventana.
La posición física exacta depende del ejemplar y de su calibración.

Las pausas del servo se programan con `millis()`, sin `delay(1500)`. La lectura
del eco sí puede ocupar hasta 30 ms; si retrasa un paso, el siguiente sigue
siendo de un grado y no intenta recuperar varios pasos de golpe.

## Entornos separados

| Entorno PlatformIO | Fuente compilada | Uso |
| --- | --- | --- |
| `esp32dev` | `firmware/src/main.cpp` | Aplicación principal, predeterminada |
| `hardware-diagnostic` | `firmware/src/diagnostics/main.cpp` | Prueba local de sensor y servo |

Ambos seleccionan la placa `esp32doit-devkit-v1`. Los filtros de fuentes excluyen
el otro punto de entrada, evitando dos definiciones de `setup()` y `loop()`.
La dependencia `madhephaestus/ESP32Servo@3.2.1` solo se instala para el diagnóstico.
La biblioteca está destinada a Arduino ESP32 3.x y la plataforma fijada
`platformio/espressif32@8.0.0` utiliza Arduino ESP32 3.3.12. Referencias:
[biblioteca ESP32Servo](https://github.com/madhephaestus/ESP32Servo),
[plataforma](https://github.com/platformio/platform-espressif32/releases/tag/v8.0.0)
y [placa DOIT en PlatformIO](https://docs.platformio.org/en/latest/boards/espressif32/esp32doit-devkit-v1.html).

## Compilar, sin conectar la placa

Desde la raíz del repositorio, en PowerShell:

```powershell
$pioDiagnostico = "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe"
& $pioDiagnostico run --project-dir firmware --environment hardware-diagnostic
```

La primera compilación puede descargar la plataforma y las bibliotecas. El
binario quedará en `firmware/.pio/build/hardware-diagnostic/firmware.bin`.
En la terminal de PlatformIO también puedes usar `pio` en lugar del ejecutable
completo si ya está en el PATH. En VS Code, la tarea equivalente es
**Project Tasks → hardware-diagnostic → General → Build**.

## Cargar manualmente y abrir el monitor

Ejecuta estos pasos tú cuando quieras realizar la prueba. Cierra otros monitores
serie y usa `device list` para identificar el puerto; `COM7` es solo un ejemplo.

```powershell
& $pioDiagnostico device list
$puertoDiagnostico = "COM7"
& $pioDiagnostico run --project-dir firmware --environment hardware-diagnostic --target upload --upload-port $puertoDiagnostico
& $pioDiagnostico device monitor --port $puertoDiagnostico --baud 115200
```

En el monitor deben aparecer lecturas como:

```text
Distancia: 42.5 cm | eco: 2465 us
Distancia: sin eco (timeout de 30 ms), lectura invalida.
```

Envía `s` para probar el servo y `x` para cancelar. Abrir el monitor puede
reiniciar la placa; el servo volverá a esperar `s`. Usa `Ctrl+C` para cerrar
el monitor antes de otra carga. Si el cargador queda en `Connecting...`, mantén
BOOT pulsado al iniciar la conexión y suéltalo al comenzar la transferencia.

## Restaurar la aplicación principal

Cierra el monitor y vuelve a cargar explícitamente el entorno principal:

```powershell
& $pioDiagnostico run --project-dir firmware --environment esp32dev
& $pioDiagnostico run --project-dir firmware --environment esp32dev --target upload --upload-port $puertoDiagnostico
```

No hace falta borrar archivos, cambiar filtros o limpiar la flash. Seleccionar
el entorno para compilar no reemplaza por sí solo lo que hay en la placa: para
restaurarlo físicamente es necesaria esa segunda carga manual.

Actualmente la aplicación principal del repositorio es un esqueleto inerte.
Restaurarla significa volver a ese esqueleto; no recuperar un programa anterior
ajeno al repositorio. Si quieres conservar otro programa que ya tengas, conserva
su proyecto o binario antes de reemplazarlo.

## Pruebas de la secuencia en el PC

Con G++ disponible, sin ESP32 ni puerto serie:

```powershell
New-Item -ItemType Directory -Path firmware/.pio/host-tests -Force | Out-Null
g++ -std=c++11 -Wall -Wextra -Werror -pedantic -I firmware/include firmware/test/diagnostics/test_servo_sequence.cpp -o firmware/.pio/host-tests/servo_sequence_tests.exe
if ($LASTEXITCODE -eq 0) { & .\firmware\.pio\host-tests\servo_sequence_tests.exe }
```

Se comprueban rango, objetivos, pasos unitarios, pausas, ausencia de repetición,
cancelación, retrasos del bucle y desbordamiento del reloj. Esto prueba la lógica
de consignas; la medición física y el movimiento se verifican en la prueba manual.

## Verificación realizada

Se compilaron correctamente `hardware-diagnostic` y `esp32dev` con plataforma
8.0.0, Arduino ESP32 3.3.12 y ESP32Servo 3.2.1 en el diagnóstico. Las pruebas
C++ de la secuencia pasaron en el PC. La dependencia ESP32Servo emitió avisos
de variables no utilizadas; no impidieron la compilación y no se modificó la
biblioteca descargada. No se cargó ningún binario ni se abrió un puerto serie.
