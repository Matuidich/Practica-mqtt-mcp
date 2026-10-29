# Auditoría final de SIS-234 — 29 de octubre de 2026

Fuente principal: [enunciado oficial completo](../Pr%C3%A1ctica_MQTT%20%281%29.md).
Auditoría iniciada a las 16:19 de Bolivia (UTC−4). Entrega oficial: **hoy,
29 de octubre de 2026, hasta las 17:45 de Bolivia (21:45 UTC)**.

**Dictamen:** RF1–RF6 tienen respaldo en la captura real o en la demostración
física manual confirmada por el grupo. La entrega todavía está bloqueada:
**no hay remoto GitHub, commits, archivos seguidos ni aportes individuales
registrados en Git**. Exactitud, latencia instrumental y reconexión real siguen
pendientes; la frecuencia observada no sustituye la declaración de un mínimo.

Este documento es una auditoría de trabajo, no un informe técnico exigido por
el docente. No asigna una nota ni sustituye la Demo y la Defensa Individual.

## Criterio de clasificación

- **CUMPLIDO:** existe respaldo concreto en el alcance indicado. Cuando es una
  prueba manual, se identifica como declaración del grupo sobre el prototipo real.
- **PARCIAL:** existe implementación o parte de la evidencia, pero falta completar
  una condición oficial.
- **PENDIENTE:** no se realizó la acción o medición requerida.
- **NO VERIFICABLE:** la inspección local no permite certificar ese punto.

Los estados de código/documentación se refieren a los archivos locales.
**Ninguno equivale a que esos archivos ya estén entregados en GitHub.**
Las comillas de las matrices reproducen el requisito o cláusula oficial;
las descripciones de evidencia y lo que falta son conclusiones de esta auditoría.

## Matriz: sistema y requisitos funcionales

| Requisito oficial exacto | Estado | Archivo o evidencia concreta | Qué falta o límite |
| --- | --- | --- | --- |
| Modalidad: «grupos de 2 o 3 integrantes» | CUMPLIDO | [README](../README.md): Mateo Rojas y Lucia Escobar | Registrar aportes reales de ambos en commits propios; ver §6 |
| §3: «1 Objeto Inteligente con sensor ultrasónico y actuadores (mínimo 3 LEDs o 1 servomotor), con un MCU con conectividad WiFi.» | CUMPLIDO | [integrated](../firmware/src/integrated/main.cpp), [PlatformIO](../firmware/platformio.ini), [cableado](esp32-integrado.md) y confirmación física del grupo | Una placa DOIT DevKit V1, HC-SR04 y tres LEDs. El servo es una alternativa, no una obligación adicional |
| §3: «1 aplicación móvil que implemente el protocolo MQTT (p. ej. IoT MQTT Panel).» | CUMPLIDO | [Validación funcional manual](validacion-final.md#validación-funcional-manual) | IoT MQTT Panel usado con la placa real; sin registro audiovisual guardado |
| §3: «1 broker MQTT en la nube de uso libre (p. ej. HiveMQ).» | CUMPLIDO | Configuración local comprobada y [captura real](../evidence/estabilidad-02/summary.json); broker `broker.hivemq.com:1883` | Resultado de una sesión; no es garantía de disponibilidad futura del broker |
| §3: «1 herramienta de IA (p. ej. Claude Desktop) conectada al sistema mediante un servidor MCP desarrollado por el grupo.» | CUMPLIDO | [Servidor MCP](../mcp-server/iot_mcp/server.py), registro Codex inspeccionado y demostración manual confirmada por el grupo | Codex es la herramienta elegida; Claude Desktop es un ejemplo. La auditoría no abrió otra conexión |
| §3: «Todos los clientes se conectan al broker; ningún componente se comunica directamente con el objeto inteligente.» | CUMPLIDO | [WifiMqttConnection](../firmware/include/distributed/WifiMqttConnection.h), [gateway MCP](../mcp-server/iot_mcp/mqtt_gateway.py), [arquitectura](arquitectura.md) | El control documentado pasa por el broker; no se usa control serie o HTTP directo desde móvil/MCP |
| RF1: «Medir la distancia entre el sensor ultrasónico y un objeto.» | CUMPLIDO | [AsyncHcsr04](../firmware/include/distributed/AsyncHcsr04.h), [integrated](../firmware/src/integrated/main.cpp#L65) y [600 lecturas reales](../evidence/estabilidad-02/events.jsonl) | La existencia de lecturas no demuestra su exactitud contra una referencia física |
| RF2: «Publicar periódicamente la distancia medida en un tópico del broker MQTT en la nube.» | CUMPLIDO | [Publicación en integrated](../firmware/src/integrated/main.cpp#L113), [resumen original](../evidence/estabilidad-02/summary.json) | 600 lecturas únicas en 600.016 s; frecuencia media observada 0.999973 Hz; QoS 0 no permite calcular pérdida exacta |
| RF3: «Estar suscrito a un tópico de comandos y activar/desactivar sus actuadores según los comandos recibidos.» | CUMPLIDO | [Suscripción](../firmware/src/integrated/main.cpp#L85), [callback y GPIO](../firmware/src/integrated/main.cpp#L90), demostración manual de LEDs | El grupo verificó encendido/apagado real. `applied` por sí solo solo acredita consigna GPIO; la copia de ejemplo mantiene las salidas bloqueadas |
| RF4: «Desplegar la información del sensor de manera gráfica, no textual (p. ej. gráfico de línea, indicador tipo gauge o barra).» | CUMPLIDO | [Demostración manual confirmada](validacion-final.md#validación-funcional-manual): gauge de IoT MQTT Panel que cambia al acercar/alejar objetos | No hay captura de pantalla o video guardado. Debe mostrarse el gauge funcionando en la Demo |
| RF5: «Enviar comandos al objeto inteligente para activar/desactivar sus actuadores.» | CUMPLIDO | [Demostración manual confirmada](validacion-final.md#validación-funcional-manual): botones rojo, amarillo, verde y apagar todos | Los tres LEDs respondieron físicamente; sin registro audiovisual guardado |
| RF6: «Interpretar instrucciones en lenguaje natural para mostrar los datos del sensor y para ejecutar comandos sobre los actuadores del objeto inteligente, a través de las herramientas expuestas por el servidor MCP.» | CUMPLIDO | [DeviceTools](../mcp-server/iot_mcp/tools.py), [registro MCP verificado](#registro-mcp-verificado) y demostración manual informada por el grupo | Codex devolvió una lectura aproximada de 10,05 cm y ejecutó solicitudes de encendido con respuesta física. No hay transcripción/video guardado; repetir ambos tipos de solicitud en la Demo |
| §3.1: «Cada grupo deberá definir y documentar sus propios tópicos, formato de mensajes y herramientas MCP» | CUMPLIDO | Tablas del [README](../README.md), [contrato](mqtt.md), [server.py](../mcp-server/iot_mcp/server.py) y [tools.py](../mcp-server/iot_mcp/tools.py) | Se verificaron los seis nombres y parámetros contra el código, no contra nombres supuestos |
| §3.1: «los tópicos deben incluir un prefijo único del grupo para no interferir con otros grupos.» | CUMPLIDO | Prefijo UUID `sis234/2026/3a91a2d6-974c-4879-b67e-3ba4a37c201d`; [metadatos originales](../evidence/estabilidad-02/session.json), comprobación local de configuración | Los seis roles configurados tienen identificadores MQTT diferentes. El UUID del tópico no es una contraseña |

Las comprobaciones manuales fueron confirmadas expresamente por el grupo
durante esta auditoría. No se infiere RF4/RF5/RF6 de los tests ni se afirma que
existan archivos audiovisuales que no se guardaron.

## Matriz: requisitos no funcionales y calidad

Los números que el docente llama «referencia» no se convierten aquí en umbrales
obligatorios. Sí son obligatorias la declaración de valores medibles y su
verificación durante la Demo. La frecuencia de referencia de 2 lecturas/s no
autoriza a presentar el resultado de aproximadamente 1 Hz como si fuera 2 Hz.

| Requisito oficial exacto | Estado | Archivo o evidencia concreta | Qué falta o límite |
| --- | --- | --- | --- |
| §3.2: «Cada grupo deberá declarar en el README del repositorio (§4.2) y verificar durante la Demo al menos los siguientes atributos, con valores medibles» | PARCIAL | [Cinco requisitos del README](../README.md#cinco-requisitos-no-funcionales), [validación](validacion-final.md) | Falta error máximo/rango de trabajo declarado y medido; mínimo formal de frecuencia; cuantificar respuesta y verificar reconexión física |
| «Estabilidad: operación continua durante un tiempo mínimo declarado (referencia: ≥ 10 minutos) sin reinicios ni bloqueos.» | CUMPLIDO | Objetivo 600 s; [summary.json original](../evidence/estabilidad-02/summary.json) y [events.jsonl](../evidence/estabilidad-02/events.jsonl) | 600.016 s, 600 válidas/únicas, 60 en cada minuto completo; 0 silencios >3 s, interrupciones y duplicados; sin reinicio detectado por uptime. Respalda esa ventana de telemetría, no toda situación futura ni una medición directa de alimentación |
| «Exactitud de medición: error máximo respecto a una referencia física, p. ej. una cinta métrica (referencia: ≤ ±3 cm dentro del rango de trabajo declarado).» | PENDIENTE | [README](../README.md), [procedimiento con cinta](validacion-final.md#3-exactitud-contra-cinta-métrica); `reference_cm=null` en la captura | Declarar error máximo aceptado y rango de trabajo; medir contra cinta y guardar datos. El rango permitido por el código, 2–400 cm, no es un rango físicamente validado. La lectura informada de 10,05 cm no es una referencia con cinta |
| «Tiempo de respuesta: el actuador debe reflejar un comando enviado desde la aplicación móvil en un tiempo máximo declarado, medido de extremo a extremo: aplicación → broker → objeto inteligente (referencia: ≤ 1 s).» | PARCIAL | Objetivo ≤1 s y [observación visual documentada](validacion-final.md#5-latencia-física-desde-iot-mqtt-panel) | Respuesta visual prácticamente inmediata, observación manual real. Sin cronómetro ni video; no está demostrado cuantitativamente ≤1 s ni se conoce mediana/p95/máximo |
| «Frecuencia de publicación: número mínimo de lecturas publicadas por segundo declarado (referencia: ≥ 2 lecturas/s).» | PARCIAL | [Captura real](../evidence/estabilidad-02/summary.json): 0.999973334044517 Hz en toda la ventana; 1000 ms configurados como referencia | Hay medición de frecuencia media recibida, pero «aproximadamente 1 Hz» no define un mínimo ni su ventana de comparación. Declarar el mínimo elegido por el grupo y contrastarlo sin redondear. 0.999973 es menor que 1.000000 si se adopta un mínimo estricto de 1 Hz |
| «Reconexión: el objeto inteligente debe restablecer automáticamente la conexión WiFi y MQTT tras una desconexión, sin intervención manual.» | PARCIAL | [WifiMqttConnection::update](../firmware/include/distributed/WifiMqttConnection.h#L48), [backoff](../firmware/include/distributed/Backoff.h), [tests integrated](../tests/test_integrated_firmware.py) | Reconexión automática implementada y probada con dobles; falta corte/restauración real y retorno automático sin reiniciar ni intervenir el ESP32. No confundir reconexión del observador con la del dispositivo |
| «El código debe ser legible, modular (orientado a objetos), documentado y conforme a las convenciones de codificación del lenguaje utilizado.» | CUMPLIDO | Clases `IntegratedApplication`, `AsyncHcsr04`, `LedController`, `WifiMqttConnection`, `MqttGateway`, `DeviceState`, `DeviceTools`; guías y pruebas | Se revisaron separación de responsabilidades, comentarios y docstrings de las fuentes principales; no se ejecutó un análisis de estilo exhaustivo de todo el historial |
| «Las credenciales (contraseña WiFi, usuario/contraseña del broker) no deben publicarse en el repositorio: se mantienen en un archivo de configuración excluido mediante .gitignore, acompañado de una plantilla de ejemplo sin valores reales.» | CUMPLIDO | [.gitignore](../.gitignore), [plantilla vacía](../firmware/include/device_config.example.h), [.env.example](../.env.example), escaneo del conjunto candidato | Contraseña WiFi real no encontrada en archivos elegibles; las copias locales están ignoradas. Revalidar antes de publicar y no incluir binarios de firmware ni el config completo de Codex |

### Qué demuestra realmente estabilidad-02

El recálculo offline con `validation.reporting.build_report` coincide en todos
los campos con el resumen original. Se conservaron sin modificación
`session.json`, `events.jsonl` y `summary.json`. El último segmento de unos
0.016 s no es un undécimo minuto completo.

`estabilidad-01` fue una captura interrumpida, sin lecturas válidas; no se cuenta
como validación aprobada. `manual-01/conditions.md` y `latency.csv` siguen siendo
formularios vacíos, no resultados. Las evidencias de `preparacion-01` son
pruebas de software con dobles, no mediciones físicas adicionales.

## Matriz: entregables §4.1 y §4.2

| Requisito oficial exacto | Estado | Archivo o evidencia concreta | Qué falta o límite |
| --- | --- | --- | --- |
| §4.1: «Se deberá presentar un prototipo completamente operativo que demuestre la integración entre el objeto inteligente, el broker MQTT en la nube, la aplicación móvil y la herramienta de IA.» | CUMPLIDO | Captura MQTT y [demostración física manual del grupo](validacion-final.md#validación-funcional-manual) | Respaldo manual de la integración funcional; la presentación evaluada por el docente sigue por realizarse |
| §4.2.1: «Código fuente documentado del objeto inteligente.» | PARCIAL | [Fuente integrated](../firmware/src/integrated/main.cpp), [módulos](../firmware/include/distributed/), [guía](esp32-integrado.md) | Existe y compila localmente; aún no hay una versión publicada en GitHub |
| §4.2.2: «Código fuente documentado del servidor MCP.» | PARCIAL | [main.py](../mcp-server/main.py), [iot_mcp](../mcp-server/iot_mcp/), [guía MCP](../mcp-server/README.md) | Existe y pasa las pruebas locales; falta publicarlo |
| §4.2.3: «plantilla de configuración del objeto inteligente (sin credenciales)» | PARCIAL | [device_config.example.h](../firmware/include/device_config.example.h), [.env.example](../.env.example) | Plantillas disponibles sin WiFi real; falta incluirlas en la entrega GitHub |
| §4.2.3: «configuración del servidor MCP en la herramienta de IA» | PARCIAL | [Plantilla Codex](../config/codex.config.toml.example) y [extracto utilizado verificado](#registro-mcp-verificado) | El extracto documenta el registro real sin copiar configuración personal completa; falta publicarlo. La plantilla desactivada no es por sí sola evidencia del registro activo |
| §4.2.3: «si la aplicación lo permite, exportación de la configuración del panel de la aplicación móvil.» | PENDIENTE | [Referencia móvil](../config/mobile.config.example.json), que no es una exportación nativa; [función anunciada por el publicador](https://play.google.com/store/apps/details?id=snr.lab.iotmqttpanel.prod) | IoT MQTT Panel documenta importación/exportación de configuración. Falta exportar el panel real, revisar y retirar credenciales e incluir el archivo. No se inspeccionó la versión instalada en el teléfono |
| §4.2.4: «Integrantes del grupo.» | CUMPLIDO | [README](../README.md): Mateo Rojas y Lucia Escobar | Contenido local correcto; publicación pendiente |
| §4.2.4: «Tópicos MQTT y formato de los mensajes.» | CUMPLIDO | [Tabla de tres tópicos reales y JSON](../README.md#tópicos-mqtt-y-mensajes), [contrato](mqtt.md) | Se comprobaron tópico/prefijo y validadores de los tres ejemplos |
| §4.2.4: «Herramientas MCP expuestas (nombre, parámetros y propósito).» | CUMPLIDO | [Tabla README](../README.md#herramientas-mcp-expuestas), `TOOL_NAMES` y firmas de `DeviceTools` | Seis herramientas, parámetros obligatorios y opcionales comprobados contra fuentes reales |
| §4.2.4: «Valores declarados de los requerimientos no funcionales (§3.2).» | PARCIAL | [Tabla de cinco requisitos](../README.md#cinco-requisitos-no-funcionales) | Faltan el valor máximo de error y rango; mínimo formal de frecuencia. No se inventaron para cerrar la tabla |
| §4.2.4: «Instrucciones para ejecutar el sistema.» | CUMPLIDO | [Configuración y ejecución manual](../README.md#configuración-y-ejecución-manual) | Comandos y rutas revisados; carga y arranque real quedan para ejecución manual autorizada por el usuario |
| §4: «no se requiere Informe Técnico» y §4.2: «El README no constituye un informe técnico ni se califica por separado» | CUMPLIDO | README breve de referencia y documentación técnica separada | Esta auditoría es material auxiliar; dedicar el tiempo restante a entrega, Demo y defensa |

## Matriz: evaluación y entrega final

| Requisito o criterio oficial exacto | Estado | Archivo o evidencia concreta | Qué falta o límite |
| --- | --- | --- | --- |
| §2.1: «MQTT (Message Queuing Telemetry Transport): modelo publicación/suscripción, broker, tópicos y niveles de QoS.» / «Herramientas de IA: agentes y MCP (Model Context Protocol).» | NO VERIFICABLE | Implementación y [guías](../README.md#archivos-del-entregable-y-documentación) disponibles | Cada integrante debe explicarlo en la defensa; pasar tests no demuestra comprensión individual |
| §2.2: «Implementa protocolos de aplicación con integración en la nube: MQTT.» / «Integra un objeto inteligente con una herramienta de IA mediante un servidor MCP.» | CUMPLIDO | RF1–RF6 y demostración manual confirmada | El docente verificará el funcionamiento durante la Demo |
| §2.3: «Disposición a realizar prácticas y ejercicios en equipo.» / «Responsabilidad en sus asignaciones y prácticas.» / «Orden, sistematicidad y disciplina durante el análisis, diseño y construcción del prototipo.» | NO VERIFICABLE | Grupo identificado y documentación organizada | La conducta y el reparto real del trabajo no se certifican leyendo el código; hoy tampoco hay historial de commits |
| §5.1: «Demo» / «Defensa Individual»: peso «1/2» cada una; «un único nivel de 0 a 4» | NO VERIFICABLE | [Rúbricas oficiales](../Pr%C3%A1ctica_MQTT%20%281%29.md) | La calificación corresponde al docente; no hay puntuaciones por separado para README o número de tests |
| §5.2, nivel 4: «El sistema opera de forma completa y estable, con toda la comunicación pasando por el broker MQTT en la nube: el sensor se visualiza gráficamente en la aplicación, los actuadores responden a los comandos de la aplicación y de la herramienta de IA, y esta atiende correctamente las instrucciones en lenguaje natural solicitadas durante la demostración. Se verifican los requerimientos no funcionales declarados, incluida la reconexión. Montaje ordenado y seguro.» | PARCIAL | Funcionamiento RF1–RF6 informado, captura real y documentación | Faltan verificaciones no funcionales y reconexión real. El orden/seguridad física del montaje y el resultado de la Demo no se certifican desde esta auditoría local |
| §5.3, nivel 4: «Responde con precisión y profundidad, explica cualquier parte del código, del circuito, de la configuración MQTT y del servidor MCP, y justifica técnicamente las decisiones tomadas. Su aporte al grupo es claro y verificable en el historial de commits del repositorio.» | PARCIAL | Código y documentación disponibles; `git log` no tiene commits | Ambos deben preparar todo el sistema y registrar aportes propios verificables; no basta que uno conozca solo su componente |
| §6: «Qué se entrega: un repositorio GitHub con el contenido descrito en §4.2.» | PENDIENTE | `git remote` vacío; usuario confirma que no existe repositorio remoto anterior | Crear repositorio nuevo y publicar el conjunto revisado antes del plazo |
| §6: «Cada integrante debe realizar commits con su propia cuenta de GitHub; el historial de commits se utiliza como evidencia de su aporte en la Defensa Individual (§5.3).» | PENDIENTE | 0 commits, 0 autores registrados; rama actual `master`, sin primer commit | Commits auténticos de Mateo y Lucia con sus respectivas cuentas y aportes reales; la auditoría no cambia identidades ni atribuye trabajo |
| §6: «el enlace del repositorio GitHub se envía por el LMS-UCB.» | PENDIENTE | No hay URL de repositorio nuevo ni comprobante de envío disponible | Un integrante debe enviar el enlace correcto por LMS y conservar el comprobante |
| §6: «hasta el jueves 29 de octubre de 2026 a las 17:45.» | PENDIENTE | Fecha oficial y reloj UTC consultado; inicio 16:19 Bolivia | Crear, publicar y enviar antes de 17:45 Bolivia; no basta tener los archivos solo en disco |
| §6: «El repositorio debe estar accesible para el docente en la fecha de entrega. Solo se evalúa el contenido existente en el repositorio hasta esa fecha; un enlace inaccesible equivale a trabajo no entregado.» | PENDIENTE | No hay remoto ni ramas remotas para verificar | Comprobar acceso del docente, rama de entrega y presencia de archivos desde GitHub; no se puede acreditar accesibilidad o envío desde este repositorio local sin publicar |

## Registro MCP verificado

Se leyó la entrada `sis234-iot` de la configuración local de Codex, sin ejecutar
herramientas ni iniciar un cliente MQTT. El comando y el argumento `main.py`
existen. No hay `env` ni `env_vars` adicionales en esa entrada; `enabled` no está
desactivado. Extracto de los campos de ejecución utilizados, sin secretos:

```toml
[mcp_servers.sis234-iot]
command = 'M:\IOT\Practica-mqtt-mcp\.venv\Scripts\python.exe'
args = ['-u', '-B', 'M:\IOT\Practica-mqtt-mcp\mcp-server\main.py']
```

Estas rutas pertenecen a este equipo; adaptarlas en otro equipo. No copiar a
GitHub el archivo personal completo de Codex ni sus archivos de autenticación.
La [documentación oficial de OpenAI](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
confirma la configuración STDIO mediante `command` y `args` en `config.toml`.
El registro habilitado y la prueba manual de RF6 son evidencias diferentes.

## Exportación móvil pendiente

La [ficha del publicador de IoT MQTT Panel](https://play.google.com/store/apps/details?id=snr.lab.iotmqttpanel.prod)
anuncia importación/exportación de la configuración. Por tanto, la condición
de §4.2 no permite omitir este archivo sin comprobar la versión utilizada.
El publicador también describe la exportación a archivo desde los ajustes de
la aplicación; el nombre exacto del menú puede variar según la versión.

El grupo debe guardar la exportación real del panel, revisar que no contenga
contraseñas, tokens u otros secretos, e incorporarla después de esa revisión.
No se debe compartir mediante MQTT durante esta auditoría. Si la versión
instalada impide exportar, registrar versión y limitación concreta, sin
presentar `mobile.config.example.json` como si fuera una exportación nativa.

## Comprobaciones locales seguras realizadas

| Comprobación | Resultado real de esta auditoría | Alcance |
| --- | --- | --- |
| `.venv\Scripts\python.exe -B -m unittest discover -s tests -v` | **131 pruebas correctas**, sin fallos ni omisiones; 25.419 s | Python, C++ y protocolo STDIO con dobles; no demuestra por sí solo hardware ni red real |
| `.venv\Scripts\python.exe -B -m iot_shared check` | **Configuración local válida** | Coherencia del `.env` y los dos archivos derivados; no los reescribe |
| PlatformIO `run -d firmware -e integrated` | **SUCCESS**, comprobación incremental del build actual; 4.418 s | ESP32 DOIT DevKit V1; RAM estática 47 800 B y flash 969 876 B. No se cargó firmware ni se abrió serie |
| Recálculo offline de `estabilidad-02` | Coincidencia exacta con el resumen original | No se regeneró ni modificó ningún JSON original |
| Tópicos y herramientas del README | Tres tópicos/JSON válidos; seis nombres y firmas MCP coincidentes | Revisión de código y validadores compartidos |
| Credenciales y exclusiones | Copias locales ignoradas; sin contraseña WiFi real ni claves/tokens detectados en el conjunto candidato | Se revisó una coincidencia lexical contextual que no era configuración de red. No se copia ningún valor WiFi a esta auditoría |
| Copia local de hardware | LED habilitado localmente; rojo 25, amarillo 26, verde 27; TRIG 5, ECHO 18 | Solo lectura, sin divulgar WiFi. La plantilla conserva `LED_WIRING_CONFIRMED=false`; la compilación no prueba qué binario está cargado en la placa |

La primera compilación encontró un bloqueo de escritura del sandbox en el
directorio de PlatformIO. Se repitió con la autorización del entorno y terminó
correctamente. No fue un error de firmware. Los tests bloquean sockets/DNS o
usan MQTT falso. No se envió ninguna orden física, se flasheó, se abrió serie,
se reinició la placa ni se interrumpió una sesión existente.

## Estado Git y archivos para publicar

La inspección inicial encontró **0 archivos seguidos, 0 commits, ninguna
referencia local/remota confirmada y ningún remoto configurado**. `master` es
el nombre de la rama inicial todavía sin commit; no hay upstream. El usuario
confirmó que el proyecto es nuevo y no existe una versión publicada anterior.

- [Manifiesto exacto para incluir](archivos-incluir-github.txt): fuentes,
  pruebas, documentación, plantillas, enunciado y solo los tres originales de
  `evidence/estabilidad-02`. Incluye también esta auditoría y sus dos listas.
- [Exclusiones reales por archivo/directorio completo](archivos-excluir-github.txt):
  las copias locales, entornos, cachés, build y demás evidencias locales.
  Un directorio en esa lista excluye todos sus archivos descendientes.
- No incluir `.env`, WiFi local, cabecera MQTT generada, referencia móvil local,
  `.venv`, `.pio`, cachés ni configuración personal completa de Codex.
  **Los binarios compilados pueden contener las credenciales WiFi**: tampoco
  subir `firmware.bin`, `.elf`, volcados o archivos de compilación con esos datos.
- `AGENTS.md` y las alternativas históricas no son exigencias del docente;
  se conservan como material de desarrollo. Algunas notas históricas de etapa
  no describen el estado funcional actual; prevalecen las comprobaciones y
  evidencias identificadas aquí.

Tras preparar la documentación, el manifiesto contiene **119 archivos exactos**.
Las exclusiones contienen **10 rutas** que cubren los **9.615 archivos ignorados**
observados. Es un inventario del momento de la auditoría, no una lista que se
actualice automáticamente si se crean archivos nuevos.

No se eliminó ningún archivo. Mantener una copia local de todas las evidencias
excluidas. Una nueva exportación móvil o medición no entra automáticamente en
el manifiesto revisado: comprobar su contenido y actualizar la lista antes de
añadirla. No utilizar `git add -f` para saltarse las exclusiones.

## Acciones urgentes, en orden de prioridad

1. **P0 — Entrega:** crear el repositorio GitHub vacío, preparar commits reales
   de ambos integrantes, publicar los archivos revisados y comprobar acceso.
   Enviar el enlace por LMS antes de las 17:45 Bolivia. Esto bloquea la entrega
   aunque el prototipo funcione.
2. **P1 — Valores y verificaciones pendientes:** declarar máximo de error/rango
   y mínimo de frecuencia, sin inventar resultados; hacer medición con cinta,
   medición de respuesta y prueba real de reconexión solo si el grupo puede
   ejecutarlas manualmente con tiempo suficiente. Preservar resultados fallidos.
   No alterar firmware, intervalo o credenciales para maquillar el resultado.
3. **P1 — Configuración móvil:** exportar el panel real desde la app y revisar
   secretos; si la versión instalada lo impide, registrar la limitación concreta.
   La referencia JSON actual no es una exportación nativa del panel.
4. **P2 — Demo y defensa:** mostrar gauge variable, comandos móviles de los tres
   LEDs y apagar todos, lectura y control mediante lenguaje natural en Codex;
   ambos integrantes deben explicar todo el circuito/código, MQTT, MCP, QoS 0,
   `command_id`, alcance de `applied`, pines y reconexión. Tener las evidencias
   originales a mano. No asumir que esta auditoría garantiza nivel 4.

## Cómo dejar listo un repositorio GitHub nuevo

**Los pasos siguientes son para ejecución manual posterior. Esta auditoría no
hizo staging, commits, push, merge, cambios de identidad ni creación de remoto.**

1. Revisar ambas listas y el estado. Para previsualizar exactamente el conjunto
   recomendado, sin añadirlo al índice:

   ```powershell
   git status --short --branch
   git add -n --pathspec-from-file=docs/archivos-incluir-github.txt
   ```

2. Cada integrante debe usar su propia cuenta/identidad verificada de GitHub y
   registrar con un commit su aporte real. Revisar los archivos seleccionados
   antes de cada commit; no atribuir aportes del otro integrante. El manifiesto
   puede usarse para añadir el conjunto revisado, distribuyendo los commits
   según la autoría real y comprobando los cambios antes de confirmar:

   ```powershell
   git add --pathspec-from-file=docs/archivos-incluir-github.txt
   git diff --cached --name-only
   git diff --cached --check
   ```

   No ejecutar ese `git add` global si corresponde seleccionar primero solo el
   aporte de un integrante. Este documento no decide la identidad ni el reparto
   de autoría. Tras los commits reales, comprobar autores e inventario con:

   ```powershell
   git log --format="%h | %an | %s"
   git ls-tree -r --name-only HEAD
   ```

3. Crear en GitHub un repositorio **vacío**, sin README/.gitignore iniciales.
   Usar la URL real del nuevo repositorio. Los comandos de ejemplo conservan
   `master`, la rama local observada, para evitar publicar una rama inexistente:

   ```powershell
   git remote add origin https://github.com/CUENTA/REPOSITORIO.git
   git push -u origin master
   ```

4. Verificar en GitHub la rama entregada y todos los archivos del manifiesto,
   incluidos los tres originales de `estabilidad-02` y commits de ambos. Si es
   privado, confirmar que el docente tenga acceso. No publicar configuración
   local ni binarios. Verificar que el enlace abre desde el acceso previsto
   para el docente y enviarlo por LMS antes del plazo; basta un integrante.

Un remoto configurado no significa contenido publicado; un push correcto no
significa enlace enviado por LMS. Esas tres comprobaciones deben cerrarse por
separado y antes de las 17:45.
