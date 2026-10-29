# Pruebas de firmware en el PC

Desde la raíz: `python -B -m unittest discover -s tests -v`.
Con G++ se compila C++11 con -Wall -Wextra -Werror -pedantic en carpetas temporales;
si falta se omiten explícitamente sus casos. No usar pio test sobre hardware.

- integrated/test_integrated.cpp incluye el entorno integrado real. Dobles de
  interrupciones, reloj, colas y tarea permiten probar comandos durante ECHO,
  bloqueo LED con distancias activas, reintentos, lecturas recientes, reconexión,
  timeout, rangos, desbordamientos y fallos al reservar recursos. No ejecuta hilos
  ni interrupciones físicas: simula intercalados deterministas en el PC.
- leds/test_led_actuator.cpp incluye la aplicación LED real. Solo GPIO, reloj,
  configuración y transporte se sustituyen por dobles. Comprueba encendido y
  apagado individual, cambios parciales, combinados y exclusivos, confirmación
  completa, validación, duplicados, desconexión, reintentos y cableado bloqueado.
  También compara el parser y las ocho combinaciones de estado contra Python.
- leds/test_connection.cpp prueba WifiMqttConnection real con dobles Wi-Fi,
  TCP y PubSubClient: reconexión, backoff y restauración de commands/leds.
  El compilador comprueba que las pruebas no dependan de cabeceras locales reales.
- distributed/test_distributed.cpp conserva pruebas de mensajes y políticas
  portables, incluyendo la rampa histórica y backoff.
- actuator/test_actuator.cpp ahora incluye history/servo/main.cpp: regresiones
  históricas de retención PWM y protecciones SG90, nunca firmware activo.
- diagnostics/test_servo_sequence.cpp conserva el diagnóstico anterior.

Los dobles no crean sockets ni abren GPIO o serie. Estas pruebas no validan la
corriente, luz emitida o comportamiento real de HiveMQ. La integración física
y de red queda pendiente de una ejecución manual separada.
