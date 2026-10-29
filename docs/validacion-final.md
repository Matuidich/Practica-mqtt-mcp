# Validación final medible de SIS-234

El prototipo funcional reportado por el usuario es una placa ESP32 con firmware
`integrated`, HC-SR04, tres LEDs, IoT MQTT Panel y MCP en Codex. Esta guía documenta
la primera captura real de estabilidad y frecuencia, realizada el 2026-10-29,
y conserva los procedimientos para las mediciones pendientes de la Demo.
Las cifras del docente son referencias, no requisitos de aprobación. Anotar las
referencias y los criterios que el grupo elija antes de medir; informar también
los resultados que sean diferentes, sin sustituirlos por valores esperados.

## Primera validación real: estabilidad y frecuencia

**Objetivo declarado:** observar la recepción de distancias durante una ventana
de 600 s y caracterizar su frecuencia real, registrando silencios mayores de 3 s,
interrupciones del observador, duplicados y eventos de uptime compatibles con
reinicio. La sesión registra un intervalo configurado de referencia de 1000 ms
(aproximadamente 1 Hz); no es un umbral de aprobación ni una frecuencia medida.

La captura `estabilidad-02` tiene modo `live_mqtt_observation`, propósito
`stability`, dispositivo `sensor-01` y estado `completed`. La sesión comenzó el
2026-10-29 a las 19:21:35.995162 UTC; la ventana de medición comenzó después de
confirmarse la suscripción.

| Medición | Resultado real | Campo del resumen original |
| --- | --- | --- |
| Duración (objetivo: 600 s) | 600.016 s | `actual_duration_s` |
| Mensajes de distancia recibidos | 600 | `distance_messages_received` |
| Lecturas válidas / únicas | 600 / 600 | `valid_messages` / `unique_readings` |
| Frecuencia en toda la ventana | 0.999973 Hz (aproximadamente 1 Hz) | `frequency_hz_whole_window` |
| Lecturas por minuto completo | 60 en cada uno de los 10 minutos completos | `per_minute` |
| Silencios mayores de 3 s | 0 | `long_silences` (vacío) |
| Interrupciones del observador | 0 | `observer_outages` (vacío) |
| Duplicados | 0 | `duplicate_messages` |
| Reinicios detectados | Ninguno según el uptime observado | `device_uptime_events` (vacío) |

Metodología aplicada al registro:

1. El observador independiente se suscribió únicamente al tópico de distancia
   del dispositivo seleccionado, con MQTT 3.1.1 y QoS 0. Los metadatos y eventos
   conservan la suscripción y los tiempos de la ejecución real.
2. La ventana empezó tras SUBACK. La duración se calculó con el reloj monotónico
   entre `window_start` y `window_end`, incluyendo los márgenes hasta la primera
   y desde la última lectura; el cierre fue completo e intencional.
3. Las lecturas se validaron con el contrato compartido y se distinguieron por
   `uptime_ms`, no por cambios de distancia. La frecuencia es `N/T`:
   `600 / 600.015999999945 = 0.999973334044517 Hz`, redondeada en la tabla.
4. Los conteos se agruparon en intervalos de 60 s desde el inicio de la ventana.
   La fracción final de aproximadamente 0.016 s tuvo 0 lecturas y no constituye
   un undécimo minuto completo. Los silencios mayores de 3 s incluyen también
   los márgenes inicial y final; se revisaron la cobertura del observador y
   los eventos de uptime.

Evidencia original de la misma captura:

- [Resumen de resultados: summary.json](../evidence/estabilidad-02/summary.json).
- [Metadatos y parámetros: session.json](../evidence/estabilidad-02/session.json).
- [Registro completo de recepciones y conexiones: events.jsonl](../evidence/estabilidad-02/events.jsonl).

El resumen coincide con el recálculo offline de los metadatos y el registro.
Los tres archivos se conservan sin modificaciones; las cifras de esta guía se
redondean solo para su presentación.

El resultado describe una sola ventana de recepción MQTT. No determina la
pérdida exacta de paquetes QoS 0 ni garantiza estabilidad fuera de esos 10 minutos.
La ausencia de reinicios detectados se basa en el uptime, no en una observación
directa de la alimentación. Las notas de la sesión están vacías: no se atribuyen
condiciones físicas o de red adicionales que no quedaron registradas.
**Exactitud con cinta, medición cuantitativa de latencia física y reconexión
WiFi/MQTT siguen pendientes**;
esta captura no proporciona resultados de esos ensayos ni una aprobación global.

## Validación funcional manual

Durante la auditoría final, el grupo confirmó estas pruebas con el prototipo
físico real. La fuente es su demostración manual informada; no se cuenta con
un registro audiovisual guardado.

| Requisito | Comprobación física informada por el grupo | Estado |
| --- | --- | --- |
| RF3 y RF5 | Botones rojo, amarillo, verde y apagar todos de IoT MQTT Panel; los tres LEDs respondieron físicamente | CUMPLIDO mediante demostración manual |
| RF4 | Gauge de IoT MQTT Panel que cambia al acercar y alejar objetos del HC-SR04 | CUMPLIDO mediante demostración manual |
| RF6 | Consulta de distancia en lenguaje natural desde Codex (lectura informada de aproximadamente 10,05 cm) y solicitudes de encendido de LEDs con respuesta física | CUMPLIDO mediante demostración manual |

La lectura informada de 10,05 cm no se comparó con cinta y no es un resultado
de exactitud. La observación de los LEDs tampoco mide el tiempo de respuesta.
Se mantienen pendientes la exactitud, la latencia instrumental y la reconexión
real. Estas demostraciones manuales no alteran la captura cuantitativa original
de `estabilidad-02` ni sustituyen la Demo que evaluará el docente.

## Herramientas reutilizadas y alcance

- `iot_shared.config.Settings`: lee exclusivamente el `.env` existente; no utiliza
  variables del proceso como sobrescrituras, ni escribe UUID, WiFi o pines.
- `iot_shared.messages.DistanceReading`: aplica exactamente el contrato vigente
  de distancia. No se duplica su validador en el observador.
- Las pruebas anteriores de firmware y gateway/MCP verifican lógica con dobles;
  se conservan. No miden exactitud física ni tiempos de la red real.
- Se reutilizan `Journal`, `DistanceObserver`, `capture_window` y los cálculos
  de `validation/reporting.py`. `tests/test_validation.py` comprueba con reloj
  y MQTT falsos una ventana de 600 s, conteos a una frecuencia diferente de
  2 Hz, interrupciones, errores, exactitud y anotaciones de video. Los datos
  ficticios quedan en carpetas temporales con modo `offline_fixture`.
- `validation/` añade un observador independiente: usa Paho 2.x ya presente en
  `requirements.txt`, MQTT 3.1.1, QoS 0, un identificador nuevo por ejecución y
  únicamente la suscripción al tópico exacto `telemetry/distance` del prefijo local.
  No llama a `publish`, no lee herramientas MCP, no abre puertos serie y no
  desconecta ni reconfigura el ESP32. Reconecta con las esperas progresivas de
  la configuración y restaura su suscripción tras cada conexión.
- Importar el paquete, `check`, `report`, `mark`, `templates`, `accuracy` y
  `latency` no abren conexiones. Solo `capture --live` inicia el observador real.
  Las pruebas por defecto siguen siendo locales.

No hay que instalar ni activar otro servidor MCP, compilar, cargar firmware,
editar `.env`, ejecutar `sync` o cambiar tópicos para estas mediciones.

## Preparación y evidencias

Todos los comandos siguientes se ejecutan en PowerShell desde
`M:\IOT\Practica-mqtt-mcp`, usando el entorno `.venv` existente. Las comprobaciones
locales son:

```powershell
& .\.venv\Scripts\python.exe -B -m validation check
& .\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
& .\.venv\Scripts\python.exe -B -m iot_shared check
```

`validation check` revisa configuración y dependencia, sin resolver DNS ni abrir
MQTT. No ejecuta una captura. Si falta Paho, usar la instalación documentada en
`requirements.txt` antes de continuar; no se necesita otra biblioteca de medición.

Se prepararon una ficha y una planilla **vacías** en `evidence/manual-01`, sin
resultados inventados. Para crear otra serie, sin red, usar una carpeta nueva:

```powershell
& .\.venv\Scripts\python.exe -B -m validation templates --output .\evidence\manual-02
```

Completar `conditions.md`: fecha, operador, alimentación, firmware cargado,
versión de Panel, topología de red, blanco y geometría, cinta y su resolución,
temperatura si se dispone de ella, cámara y FPS real. No cambiar el firmware
entre repeticiones. Mantener alimentación estable, equipo observador despierto
y simulador/otros publicadores de distancia detenidos. Confirmar que el payload
del sensor usa `device_id=sensor-01`; si se personalizó, sustituir solo el argumento
`--device-id` por el valor vigente, sin cambiar ninguna configuración.

Cada captura requiere una carpeta nueva. `estabilidad-01` y `estabilidad-02` ya
existen; para otra captura usar `estabilidad-03` si aún no existe. Nunca se
sobrescriben las evidencias anteriores. Se conservan:

| Archivo | Evidencia |
| --- | --- |
| `session.json` | Propósito, reloj, duración solicitada, dispositivo, versiones, tópico de distancia, intervalo configurado como referencia y notas |
| `events.jsonl` | Una línea por recepción/evento, hora UTC, segundos monotónicos, JSON recibido, duplicados, descartes y conexiones |
| `summary.json` | Conteos, duración real, frecuencia, intervalos, silencios y resultados que correspondan al propósito |
| `markers.jsonl` | Solo en reconexión: marcas humanas de corte/restauración y su incertidumbre si se declara |

Se vacía el registro al archivo después de cada evento. `Ctrl+C` conserva la
ventana parcial y la marca `interrupted`: no cuenta como una prueba completa de
600 s. Si no llega SUBACK en 30 s, la prueba no empieza y se conserva el error.
Si no se recibe ninguna lectura, se informa explícitamente; no se inventa una.
Un cierre forzado o corte eléctrico podría dejar una última línea incompleta;
el analizador lo rechaza en vez de ignorarlo silenciosamente. Conservar el
original y documentar cualquier recuperación manual en una copia.

`evidence/` se ignora por defecto. La única excepción en `.gitignore` son los tres
archivos revisados de `estabilidad-02`: `session.json`, `events.jsonl` y
`summary.json`. Pueden incorporarse al repositorio junto con esta documentación,
sin forzar su inclusión. La revisión no encontró credenciales, SSID, contraseñas,
tokens ni claves privadas; contienen el tópico con su prefijo UUID identificador
y la telemetría del sensor. Ese prefijo es visible para quien acceda al repositorio.

Las demás capturas, fotos, videos originales, planillas y fichas siguen ignorados.
Guardarlos localmente y hacer una copia de respaldo fuera del repositorio.
No copiar `.env`, cabeceras locales de WiFi ni claves como evidencias. Revisar
cada nueva evidencia antes de añadir una excepción específica; la excepción
actual no habilita otros archivos de la carpeta ni futuras capturas.

## 1. Estabilidad durante 10 minutos

Para una repetición manual, colocar un blanco plano fijo, perpendicular y dentro
del rango útil. No moverlo, no hacer cortes de red y no enviar órdenes durante
esta prueba. Usar una carpeta nueva; la primera captura completa documentada
permanece en `estabilidad-02`:

```powershell
& .\.venv\Scripts\python.exe -B -m validation capture --live --purpose stability --duration-s 600 --device-id sensor-01 --gap-s 3 --output .\evidence\estabilidad-03
```

El contador de 600 s empieza después del SUBACK, que confirma la suscripción del
observador. El tiempo de conexión inicial queda registrado aparte. La ventana
incluye los intervalos hasta la primera y desde la última lectura. La duración
real puede exceder ligeramente 600 s por la planificación del sistema y queda
registrada. El programa informa progreso cada 30 s y termina automáticamente.

En `summary.json` consultar:

- `measurement_status`, `actual_duration_s` y `data_observed`.
- `distance_messages_received`: todos los mensajes del tópico recibidos dentro
  de la ventana. `valid_messages` incluye duplicados; `unique_readings` los excluye.
  Se separan mensajes inválidos, retained y de otro dispositivo.
- `long_silences`: intervalos mayores que `--gap-s`, incluidos inicio y final;
  sus instantes permiten cotejarlos con el video o las notas.
- `observer_outages`: intervalos en que el propio observador no estaba suscrito.
  Durante ellos no se puede saber si el ESP32 siguió publicando.
- `per_minute` y `device_uptime_events`: variación por minuto y regresiones de
  uptime compatibles con reinicio o reordenación. El desbordamiento uint32 se
  distingue por proximidad al límite; esta identificación es una heurística.

Los 3 s del ejemplo son una regla explícita para **detectar silencios**, ajustable
con `--gap-s`. No son un umbral del docente ni una prueba de estabilidad aprobada.
Después de conocer la frecuencia real, elegir para las siguientes pruebas un
`--gap-s` mayor que el intervalo normal observado y anotar el criterio. Si se
cambia para analizar una captura anterior, trabajar sobre una copia documentada
de los metadatos y conservar el original; el reporte usa el valor registrado.
Un silencio puede deberse a eco inválido, pérdida QoS 0, red, broker o receptor:
el registro por sí solo no atribuye la causa. Sin número de secuencia y sin
instrumentar el publicador no se puede calcular la pérdida exacta de paquetes
ni el número de publicaciones que el ESP32 intentó enviar.

Código de salida 0 significa captura completa con alguna lectura; 2 significa
captura interrumpida o sin lecturas; 1 indica error de ejecución. **Ningún código
declara aprobados los atributos de la práctica.**

## 2. Frecuencia real de publicaciones

La misma captura de estabilidad ya mide frecuencia; no hace falta otra conexión.
Opcionalmente se puede repetir con `--purpose frequency` y una carpeta nueva.

- `frequency_hz_whole_window = N/T`, donde N es el número de lecturas distintas
  recibidas y T la duración monotónica real completa, incluyendo silencios.
- `frequency_hz_first_to_last = (N-1)/(t_última-t_primera)` cuando hay al menos
  dos lecturas con instantes diferentes. También incluye los huecos entre ellas.
- `receive_interval_s`: media, mediana, p95, mínimo, máximo y desviación muestral
  de los intervalos entre llegadas. `per_minute` permite ver cambios en el tiempo.
- `device_uptime_interval_s` compara intervalos del reloj del ESP32 entre lecturas
  observadas, sin cruzar una regresión/reinicio. No sincroniza ese reloj con el PC.

Se conservan los números sin redondear en JSON. El p95 usa interpolación lineal
en `0.95*(n-1)`; con pocos datos se debe indicar el tamaño de muestra. El intervalo
configurado se registra solo como referencia: ecos descartados, planificación y
red pueden cambiar la frecuencia observada. No se asumen dos publicaciones por
segundo. Dos mensajes consecutivos con el mismo uptime no constituyen una nueva
medición. Sin secuencia, la deduplicación entre reinicios/reordenaciones tiene
esa limitación; revisar los eventos de uptime antes de interpretar la frecuencia.

Recalcular cualquier captura sin conectarse, conservando el reporte original:

```powershell
& .\.venv\Scripts\python.exe -B -m validation report --run .\evidence\estabilidad-02 --output .\evidence\estabilidad-02\summary-recalculado.json
```

## 3. Exactitud contra cinta métrica

Elegir varios puntos dentro del rango de 2–400 cm del firmware. Una propuesta de
muestreo es 10, 20, 50, 100 y 150 cm: son posiciones de ensayo, **no resultados
esperados ni umbrales**. Si el espacio disponible obliga a otros puntos, anotarlos.

1. Fijar el sensor y un blanco suficientemente amplio, plano y perpendicular.
   Medir desde un plano reproducible del frente de los transductores hasta el
   blanco, describirlo y fotografiar cinta y colocación. No usar la lectura MQTT
   para decidir la distancia real.
2. Anotar la distancia efectivamente medida, resolución de la cinta, incertidumbre
   de colocación, inclinación y condiciones ambientales. Esperar a que el blanco
   esté quieto antes de capturar. No modificar calibración, firmware ni filtros.
3. Capturar por ejemplo 60 s por punto y repetir tres veces, recolocando el blanco.
   Procurar al menos 30 lecturas distintas por repetición; comprobar el conteo y
   ampliar la duración si la frecuencia real produce menos. Guardar también las
   capturas insuficientes o fallidas con su explicación.

Ejemplo **solo si la cinta indica 50 cm** (reemplazar por la referencia real):

```powershell
& .\.venv\Scripts\python.exe -B -m validation capture --live --purpose accuracy --duration-s 60 --device-id sensor-01 --reference-cm 50 --gap-s 3 --output .\evidence\exactitud-050-r1 --notes "Completar geometria y condiciones en la ficha manual"
```

Se puede añadir `--reference-uncertainty-cm VALOR` con una incertidumbre estimada
real. Si no se conoce, queda `null`; el programa no la inventa. Cambiar el nombre
de carpeta para cada punto/repetición. El reporte calcula, para cada lectura
`e = distancia_HC-SR04 - distancia_cinta`: sesgo medio, MAE, RMSE, mayor error
absoluto, MAE porcentual y desviación muestral como repetibilidad. Con una sola
lectura no se calcula desviación. La incertidumbre de cinta se registra como
contexto y no se propaga automáticamente a los errores.

Agrupar las capturas ya realizadas, sin red (añadir un `--run` por cada una):

```powershell
& .\.venv\Scripts\python.exe -B -m validation accuracy --run .\evidence\exactitud-050-r1 --run .\evidence\exactitud-050-r2 --run .\evidence\exactitud-050-r3 --output .\evidence\exactitud-resumen-01.json
```

El resumen mantiene cada punto/repetición y métricas globales que ponderan cada
lectura igual. Si los tamaños difieren, considerar también cada punto por
separado. No mezcla capturas ficticias con reales ni acepta capturas incompletas,
sin lecturas/referencia o con cortes del observador. No convierte una muestra
escasa en evidencia suficiente; revisar manualmente los conteos.

## 4. Reconexión WiFi y MQTT, separadas

Mantener el ESP32 alimentado, sin reiniciarlo. Mantener al observador en una
conexión independiente: por ejemplo PC con Ethernet y ESP32 con un punto de
acceso dedicado. Si ambos pierden Internet no se puede aislar la recuperación
del ESP32. No desconectar el cliente observador para simular un corte del ESP32.

- **WiFi:** el operador desactiva temporalmente el AP dedicado o la asociación
  permitida para el ESP32, y después la restaura con el mismo SSID/clave. No
  cambiar credenciales ni apagar la placa.
- **MQTT:** con WiFi asociado, el operador bloquea temporalmente solo la salida
  MQTT TCP 1883 del ESP32 en un router bajo su control y después la habilita.
  La regla debe afectar también el tráfico de la sesión TCP ya establecida.
  No tocar el broker público ni bloquear el tráfico del observador. Si no se
  dispone de ese aislamiento, declarar la prueba MQTT separada pendiente;
  cortar WiFi no demuestra por sí solo un fallo MQTT con WiFi disponible.

Un bloqueo MQTT breve puede detener entregas sin destruir la sesión TCP/MQTT.
Registrar el keepalive y las esperas de reintento del firmware, conservados como
referencias en `session.json`, y verificar el cierre de la sesión del ESP32 con
evidencia del router o una captura de red autorizada. Mantener el bloqueo hasta
observar ese cierre y los reintentos; ampliar la ventana de captura si hace falta.
No asumir que 20 s bastan para MQTT. Si solo se verifica que vuelven las lecturas,
presentar el dato como **tiempo de recuperación de publicaciones** y declarar
pendiente la comprobación de una nueva sesión. El observador no ve el handshake
del ESP32 y sus propios eventos `connected` corresponden al PC.

Captura propuesta, primero para WiFi:

```powershell
& .\.venv\Scripts\python.exe -B -m validation capture --live --purpose reconnect --duration-s 300 --device-id sensor-01 --gap-s 3 --output .\evidence\reconexion-wifi-01
```

Esperar al menos 30 s de publicaciones normales. En **otra terminal del mismo
PC**, preparar una marca; `--wait-enter` toma el instante al pulsar Enter, para
evitar usar el tiempo de arranque del comando como referencia de la acción:

```powershell
& .\.venv\Scripts\python.exe -B -m validation mark --run .\evidence\reconexion-wifi-01 --trial-id wifi-01 --event cut --cause wifi --wait-enter
```

Coordinar Enter con la acción manual que corta WiFi. Mantener el corte unos
20 s y comprobar que cesan publicaciones. Preparar la segunda marca y coordinar
Enter con la restauración:

```powershell
& .\.venv\Scripts\python.exe -B -m validation mark --run .\evidence\reconexion-wifi-01 --trial-id wifi-01 --event restored --cause wifi --wait-enter
```

Estas marcas **no cambian redes ni ejecutan órdenes**. El instante es humano:
usar dos operadores, filmar acción/Enter o estimar la diferencia e indicarla con
`--uncertainty-s VALOR` y `--notes`. Si no se cuantifica, la incertidumbre queda
desconocida; no atribuir precisión de milisegundos a una acción humana. Los relojes
de distintos equipos no sirven para estas marcas. No mover la carpeta de captura
a otro PC ni reiniciar el PC durante la sesión.

Esperar a que vuelvan publicaciones y se mantengan regulares al menos 30 s antes
de repetir con `wifi-02` y `wifi-03`. No comenzar un nuevo corte si no se recuperó
el anterior. Para MQTT, iniciar otra captura:

```powershell
& .\.venv\Scripts\python.exe -B -m validation capture --live --purpose reconnect --duration-s 300 --device-id sensor-01 --gap-s 3 --output .\evidence\reconexion-mqtt-01
```

En la otra terminal, usar estas marcas mientras el operador bloquea/restaura
manualmente el tráfico MQTT del ESP32:

```powershell
& .\.venv\Scripts\python.exe -B -m validation mark --run .\evidence\reconexion-mqtt-01 --trial-id mqtt-01 --event cut --cause mqtt --wait-enter
& .\.venv\Scripts\python.exe -B -m validation mark --run .\evidence\reconexion-mqtt-01 --trial-id mqtt-01 --event restored --cause mqtt --wait-enter
```

Ejecutar cada comando en su momento, no ambos seguidos; repetir con IDs `mqtt-02`
y `mqtt-03`. Si la recuperación requiere más tiempo que la ventana, conservar
el resultado y repetir con mayor duración.

`summary.json → reconnection` registra tiempo de corte intencional, silencio
observado y `recovery_after_restore_s`: desde la marca de restauración hasta
la primera lectura válida posterior del dispositivo seleccionado. Incluye la
reconexión, la espera a la próxima medida y su entrega al observador: no aísla el
handshake WiFi ni el MQTT, y depende de la precisión de la marca humana. Si se
declara incertidumbre, se da también un intervalo por esa incertidumbre.

Un corte del propio observador hace el ensayo inconcluso. Si no hubo un silencio
mayor que `--gap-s` **dentro del intervalo de corte**, falta una marca o no hay
una lectura de línea base reciente (a no más de `--gap-s` antes del corte), no
se declara recuperación. Un silencio que aparece únicamente después de restaurar
no demuestra el corte previsto.
Si no vuelve ninguna lectura antes del final, se conserva un límite inferior del
tiempo observado, no un valor inventado. Revisar regresiones de uptime: un
reinicio o reordenación marca el intento inconcluso; documentarlo y repetir,
porque no aísla una reconexión. Cada intento termina antes del siguiente corte:
una publicación posterior no se atribuye a la recuperación de un ensayo anterior.
Comparar al menos tres tiempos por causa, sus tamaños de muestra y limitaciones.

Estados de `reconnection` que requieren conservar la evidencia y repetir:

| Estado | Interpretación |
| --- | --- |
| `missing_baseline` / `baseline_not_recent` | No se verificó publicación normal justo antes del corte |
| `no_interruption_demonstrated` | No hay silencio suficiente durante el corte señalado |
| `observer_disconnected_inconclusive` | El PC perdió observación; no se aísla al ESP32 |
| `device_reset_or_reorder_inconclusive` | El uptime retrocedió; no se aísla la reconexión |
| `overlapping_trials` / `next_trial_before_recovery` | Se mezclaron intentos; no se asigna una recuperación posterior al anterior |
| `incomplete_markers` / `invalid_markers` | Faltan marcas válidas de corte y restauración |
| `not_recovered_in_window` | No volvió una lectura dentro de la ventana; se informa solo un límite inferior |

`recovered_observed` significa que se observó recuperación de publicaciones en
ese intento. Su tiempo no es una medición aislada del establecimiento de WiFi/MQTT.

## 5. Latencia física desde IoT MQTT Panel

El grupo observó durante el uso real que, al presionar los botones de IoT MQTT
Panel, los LEDs físicos se encienden y apagan sin retraso perceptible.

| Aspecto | Observación real y alcance |
| --- | --- |
| Objetivo declarado | Respuesta física ≤ 1 segundo desde la pulsación en IoT MQTT Panel |
| Resultado | Respuesta visual prácticamente inmediata al encender y apagar los LEDs físicos |
| Método | Observación manual durante el uso real |
| Limitación | No se midió con cronómetro ni video; el cumplimiento cuantitativo de ≤ 1 s no está demostrado |

Este resultado es cualitativo. La medición cuantitativa de latencia física sigue
pendiente; no se asignan valores en segundos o milisegundos, mediana, p95 ni máximo
a esta observación. El procedimiento siguiente queda disponible para realizar
esa medición y conservar su evidencia.

El dato `applied` de `state/leds` solo confirma niveles GPIO lógicos. Ni la
publicación local aceptada, ni la recepción MQTT, ni el tiempo de una llamada
MCP miden el cambio luminoso. El ensayo cuantitativo propuesto se hace manualmente
desde Panel.

1. Usar una cámara externa que muestre **en la misma toma** la pantalla del
   teléfono, el contacto del dedo con el botón y el LED físico. Elegir 120/240 FPS
   si se dispone de ello; anotar los FPS de captura reales. A 60 FPS cada
   fotograma representa aproximadamente 16.67 ms. Verificar que el video tiene
   cadencia constante; no usar la velocidad de reproducción de cámara lenta
   como si fuera la frecuencia real de captura.
2. Desactivar exposición automática si produce transiciones ambiguas y evitar
   saturar el LED. Fijar cámara y luz. El estado inicial debe ser el opuesto al
   solicitado, para que cada pulsación produzca un cambio visible. Usar un solo
   botón/LED por ensayo y separar intentos varios segundos. El operador acciona
   Panel manualmente; ningún script de esta guía publica órdenes.
   Anotar el tipo de botón/interruptor y si la acción se configura al tocar o
   soltar. Usar toques breves y uniformes: el origen definido como contacto
   incluye el tiempo de mantener el dedo apoyado si el envío ocurre al soltar.
3. Hacer al menos 20 intentos, alternando encendido y apagado (10 de cada uno).
   La plantilla propone rojo, pero se puede editar `color` a yellow/green y hacer
   otras series; para caracterizar los tres LEDs, repetir la serie para cada color
   usando IDs de intento distintos. Conservar intentos sin respuesta y videos no
   utilizables.
4. Revisar fotograma a fotograma el video original. Definir `start_frame` como
   el primer fotograma donde se ve contacto físico con la zona del botón, y
   `end_frame` como el primero donde aparece/desaparece la luz física solicitada.
   Usar siempre el mismo criterio e índice de fotogramas. No usar el indicador
   de estado de Panel como fin. Si el contacto no se distingue, marcar el intento
   `unusable` o volver a filmarlo, conservando ambos archivos.
5. Completar `evidence/manual-01/latency.csv` con archivo original, FPS y ambos
   fotogramas. `status=measured` requiere todos esos campos. Para `no_change`,
   indicar `observation_s` y una nota; por ejemplo, describir cuánto tiempo se
   observó sin transición. Para `unusable`, explicar la causa en `notes`. Estos
   intentos siguen en el denominador y no reciben una latencia artificial.

El analizador rechaza una plantilla vacía o estados sin completar. La fórmula
es `latencia_ms = (end_frame-start_frame)*1000/FPS`. Guarda cada intento y resume
media, mediana, p95, máximo y dispersión de los medidos. Informa los conteos
`measured`, `no_change` y `unusable` por separado. Una cota conservadora de
cuantización es ±2 fotogramas, es decir ±`2000/FPS` ms; sumar o declarar cualquier
ambigüedad adicional del operador. Un cambio en el mismo fotograma no demuestra
latencia cero: está limitado por la resolución del video.
`by_color_and_transition` resume además encendido y apagado por cada color;
mantiene los intentos fallidos aunque un grupo no tenga ninguna latencia medible.

```powershell
& .\.venv\Scripts\python.exe -B -m validation latency --input .\evidence\manual-01\latency.csv --output .\evidence\latencia-resumen-01.json
```

Si el video tiene FPS variables, no usar esta fórmula global. Obtener tiempos
de presentación de cada fotograma con una herramienta de video y documentar
ese análisis por separado, o repetir con captura de FPS constantes. Este
procedimiento no necesita sincronizar el teléfono, ESP32 y PC: ambos extremos
físicos se observan con el mismo reloj de cámara. No mide ni descompone por
separado el retardo del touchscreen, Panel, broker y firmware.

## Presentación en la Demo y actualización final del README

Para estabilidad y frecuencia ya están disponibles los tres archivos de
`estabilidad-02` enlazados arriba y los resultados incorporados al README.
El tiempo de respuesta también cuenta con la observación manual cualitativa
documentada arriba, sin demostrar todavía el objetivo cuantitativo de ≤ 1 s.
En las siguientes etapas, completar la ficha, la tabla de exactitud por punto,
tres recuperaciones por causa y el video con la planilla de latencia. Actualizar
los resultados pendientes de exactitud y reconexión y añadir la medición
cuantitativa de latencia al README solo con valores efectivamente obtenidos,
unidades, fecha, tamaño de muestra y rutas de evidencia. Mantener las limitaciones
y ensayos fallidos. Si algo no pudo medirse, declararlo pendiente; el
funcionamiento visual o las pruebas offline no sustituyen esa medición.
