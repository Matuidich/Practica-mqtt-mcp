# Referencia histórica SG90

main.cpp es la copia del actuador anterior a la migración a LEDs. Mantiene GPIO
25, rampa gradual y PWM sostenido. No es fuente de ningún entorno PlatformIO
activo. No copiarlo a src ni cargarlo sobre el montaje LED.

Sus regresiones se mantienen en firmware/test/actuator/ y
 tests/test_actuator_application.py. Los módulos ServoMotion y CommandTracker y
los mensajes servo continúan disponibles para esta referencia. El diagnóstico
hardware-diagnostic conserva por separado el servo GPIO 19.
