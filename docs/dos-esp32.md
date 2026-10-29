# Dos ESP32: sensor HC-SR04 y actuador LED

**Alternativa histórica:** el usuario eligió definitivamente una sola placa.
La guía actual es [ESP32 integrado](esp32-integrado.md). Esta página conserva
el cableado y los comandos de los entornos separados para referencia.

**Pendiente académico:** confirmar con el docente si acepta dos ESP32 como un
objeto inteligente distribuido. El sensor observa distancia y el actuador
presenta/controla tres salidas mediante un mismo sistema MQTT, móvil y MCP.
No se ha solicitado ni recibido esa aceptación desde este proyecto.

## Placas y señales

Ambas placas son DOIT DevKit V1 (`esp32doit-devkit-v1`). El nodo sensor conserva
TRIG GPIO 5 y ECHO GPIO 18 mediante divisor de tensión; no se cambia su firmware
ni su tópico `telemetry/distance`. Las placas se comunican por Wi-Fi/MQTT;
no necesitan un cable de datos entre ellas.

El nodo actuador reemplaza el SG90 por tres LEDs comunes independientes:

| Color | GPIO | Conexión en serie |
| --- | --- | --- |
| Rojo | 25 | GPIO 25 → resistencia 220–330 Ω → ánodo LED rojo; cátodo → GND |
| Amarillo | 26 | GPIO 26 → resistencia 220–330 Ω → ánodo LED amarillo; cátodo → GND |
| Verde | 27 | GPIO 27 → resistencia 220–330 Ω → ánodo LED verde; cátodo → GND |

Cada LED necesita su propia resistencia. El ánodo suele ser la pata larga y el
cátodo la corta/lado plano de la cápsula; si se cortaron las patas, comprobar la
polaridad con la ficha o un multímetro. Usar GND de la placa actuadora. Las
salidas son digitales de 3.3 V: HIGH enciende y LOW apaga. No alimentar estas
señales con 5 V, no conectar LEDs directamente sin resistencia y no dejar el
servo conectado al GPIO 25 al sustituirlo. No hay atenuación PWM ni semáforo
automático: cualquier combinación de los tres colores es válida.

## Configuración protegida

Se conservan `.env`, UUID y `device_config.local.h` de Wi-Fi. La bandera anterior
`ACTUATOR_WIRING_CONFIRMED` solo sirve a la referencia SG90 y no habilita LEDs.
Las opciones nuevas tienen estos valores por defecto:

```cpp
#define LED_WIRING_CONFIRMED false
#define LED_RED_PIN 25
#define LED_YELLOW_PIN 26
#define LED_GREEN_PIN 27
```

La plantilla contiene estas opciones. Una copia local antigua que no las tenga
compila igualmente y queda bloqueada mediante los valores de `LedSettings.h`.
No sobrescribirla con la plantilla: después de verificar físicamente el montaje,
el usuario añadirá estas definiciones en su `device_config.local.h`, cambiando
solo `LED_WIRING_CONFIRMED` a `true`. Mantener los SSID, contraseña y demás
constantes existentes. Nunca guardar la copia local en Git.

Con la bandera false no se ejecuta pinMode ni digitalWrite sobre los tres GPIO,
no se aplica ninguna orden y no hay applied. Con la bandera true, el arranque
configura las tres salidas en LOW y espera órdenes válidas. No se crea un barrido.
La lógica empieza apagada en ambos casos; un GPIO bloqueado queda como entrada,
no como una salida que garantice LOW ante un circuito externo.

## Comportamiento MQTT

El actuador usa `<prefijo>/commands/leds` y confirma por `<prefijo>/state/leds`.
El [contrato](mqtt.md) permite cambios parciales, combinados, exclusivos y apagar
todos. Aplica los cambios dentro del mismo callback después de validar el JSON;
las escrituras de los tres GPIO son secuenciales, no eléctricamente simultáneas.
La confirmación incluye el estado lógico final completo.

Una confirmación pendiente bloquea órdenes nuevas hasta aceptar su envío.
Los duplicados de la última orden no vuelven a escribir salidas. Wi-Fi y MQTT
usan esperas de reconexión progresivas limitadas y restauran la suscripción
LED en cada conexión. El estado se conserva mientras se reconecta y no persiste
tras un reinicio. PubSubClient conecta síncronamente con límites TCP/CONNACK;
no existe un bucle de reconexión sin pausa. DNS conserva los límites de la pila.

## Verificar sin hardware

Desde la raíz en PowerShell:

```powershell
python -B -m iot_shared sync
python -B -m iot_shared check
python -B -m unittest discover -s tests -v
$pioSIS234 = "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe"
& $pioSIS234 run -d firmware -e sensor -e actuator
```

Solo compilan y prueban en el PC. Los binarios quedan en
`firmware/.pio/build/sensor/firmware.bin` y
`firmware/.pio/build/actuator/firmware.bin`. Las pruebas usan dobles de GPIO,
Wi-Fi y MQTT, sin sockets ni puertos. No verifican luz ni corriente reales.

## Pasos físicos posteriores: manuales

1. Desconectar todas las alimentaciones. Retirar el SG90 del actuador.
2. Montar los tres circuitos anteriores, cada uno con resistencia y GND propio
   hacia la misma placa. Revisar GPIO, polaridad y ausencia de cortocircuitos.
3. Solo después de esa revisión, añadir las opciones LED a la copia local y
   habilitar `LED_WIRING_CONFIRMED=true`. Recompilar actuator.
4. Identificar manualmente el puerto de la placa actuadora. Cargar solamente
   ese entorno; no sobrescribir el ESP32 sensor. Mantener el emisor MQTT sin
   publicaciones automáticas y sin órdenes retenidas durante el montaje.
5. En una prueba posterior, enviar una orden por vez y esperar el mismo
   command_id en state/leds. Probar cada color, combinaciones y apagar todos.
   Si un LED no enciende, revisar polaridad, resistencia y GND; applied no prueba
   que exista corriente por el LED. Desconectar alimentación si hay calentamiento.

Comandos documentados exclusivamente para ejecución manual, desde la raíz:

```powershell
$pioSIS234 = "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe"
$puertoActuador = "COM_ACTUADOR" # Sustituir por el puerto comprobado de esa placa.
& $pioSIS234 run -d firmware -e actuator -t upload --upload-port $puertoActuador
& $pioSIS234 device monitor --port $puertoActuador --baud 115200
```

Abrir el monitor puede reiniciar la placa. Un mensaje `ESP32 actuator: LEDs`
repetido sin intervención puede indicar reinicios; revisar alimentación y
cortocircuitos. `Ctrl+C` cierra el monitor. No usar los comandos serie s/x del
diagnóstico SG90 para controlar LEDs. Nada de esto se ha ejecutado en esta etapa.

## Referencia histórica

`firmware/history/servo/main.cpp` conserva el actuador SG90 anterior con PWM
sostenido y sus validaciones. No está bajo src ni tiene un entorno activo de
carga. `hardware-diagnostic` mantiene el diagnóstico antiguo y GPIO 19.
Sus pruebas en el PC se conservan. La [guía archivada](historial/servo.md)
describe la etapa SG90 y no debe usarse para programar el actuador LED.
