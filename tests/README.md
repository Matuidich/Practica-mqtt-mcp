# Pruebas locales SIS-234

Desde la raíz con Python 3.11 y las dependencias instaladas en `.venv`:

```powershell
& .\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
& .\.venv\Scripts\python.exe -B -m iot_shared check
& .\.venv\Scripts\python.exe -B .\mcp-server\main.py --check-offline
```

| Archivo | Cobertura |
| --- | --- |
| test_integrated_firmware.py | Diez pruebas del firmware integrado real con ISR, reloj, colas y tarea MQTT dobles; medición/LED concurrentes y protección de salidas |
| test_leds.py | Mensajes LED estrictos, cambios parciales, estados, duplicados y composición MCP/simulador sin red |
| test_mcp_gateway.py | Distancia y antigüedad, combinaciones, correlación y valores de confirmación, timeouts, desconexión, suscripciones, duplicados y concurrencia |
| test_mcp_server.py | FastMCP real, seis herramientas, validación estricta, consultas durante esperas y proceso STDIO con stdout JSON-RPC y diagnóstico stderr |
| test_led_firmware.py | C++ real del actuador LED y conexión, GPIO dobles, bloqueo, reconexión y equivalencia JSON con Python |
| test_configuration.py | UUID, configuración, exportación LED/móvil y conservación de archivos locales |
| test_messages.py | Distancia sin cambios y contrato servo histórico |
| test_firmware_contract.py | C++ portable, diagnóstico y contrato anterior conservado |
| test_actuator_application.py | Referencia SG90 archivada con sus diez regresiones |
| test_offline_bootstrap.py | Importaciones inertes, errores por stderr y arranque explícito MCP con doble de servidor; simulador de red aún pendiente |
| support.py | Proyectos temporales y bloqueo de sockets/DNS por caso |
| test_validation.py | Observador sin publicaciones, SUBACK, 600 s simulados a una frecuencia distinta de 2 Hz, silencios, exactitud, reconexión sin mezclar intentos, reinicios y marcas tardías, Ctrl+C, conservación de evidencias y latencia física por fotogramas y por color/transición |

No se lee ni escribe el .env real dentro de los casos. G++ compila en carpetas
temporales; si falta, sus pruebas se omiten expresamente. Las pruebas cruzadas
usan datos ficticios, no la Wi-Fi del usuario. La comprobación CLI check es una
lectura explícita separada de la configuración local.

Integración significa aquí composición de módulos reales con dobles de transporte:
no es una prueba contra un broker real. FastMCP se inicia tanto en memoria como
por STDIO con transporte MQTT falso. Las pruebas de protocolo requieren FastMCP;
si falta se omiten explícitamente y debe usarse `.venv` para ejecutarlas todas.
La creación del cliente Paho se verifica sin iniciar su hilo de red.
`stdio_mcp_harness.py` impide construir Paho y bloquea conexiones MQTT y DNS.
Windows conserva el IPC local que necesita su event loop.

El usuario informa que sensor, LEDs, IoT MQTT Panel y MCP funcionan físicamente
con el entorno integrated. Las mediciones cuantitativas de los cinco atributos
siguen pendientes. No se envían órdenes reales, cargan firmwares ni abren puertos
serie desde esta suite. La [validación final](../docs/validacion-final.md) tiene
comandos reales separados; no forma parte de unittest. Sus pruebas nuevas usan
registros ficticios rotulados offline_fixture y reloj doble, sin esperar 10 minutos.
