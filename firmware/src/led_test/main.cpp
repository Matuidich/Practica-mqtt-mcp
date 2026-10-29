#include <Arduino.h>

namespace {
struct Led {
    int pin;
    const char* name;
};

// GPIO del ESP32, no posiciones fisicas del conector de la placa.
constexpr Led LEDS[] = {{14, "rojo"}, {26, "amarillo"}, {27, "verde"}};
constexpr unsigned long STEP_DURATION_MS = 2000;

void allOff() {
    for (const Led& led : LEDS) {
        digitalWrite(led.pin, LOW);
    }
}
}  // namespace

void setup() {
    Serial.begin(115200);
    for (const Led& led : LEDS) {
        pinMode(led.pin, OUTPUT);
        digitalWrite(led.pin, LOW);
    }
    Serial.println("led_test: GPIO directos, sin WiFi ni MQTT.");
    Serial.println("Rojo=25, amarillo=26, verde=27. HIGH=encendido, LOW=apagado.");
}

void loop() {
    for (const Led& led : LEDS) {
        allOff();
        digitalWrite(led.pin, HIGH);
        Serial.printf("LED %s: GPIO %d HIGH; los otros LOW (2 s).\n", led.name, led.pin);
        delay(STEP_DURATION_MS);
    }
    allOff();
    Serial.println("Todos apagados: GPIO 25, 26 y 27 LOW (2 s).");
    delay(STEP_DURATION_MS);
}
