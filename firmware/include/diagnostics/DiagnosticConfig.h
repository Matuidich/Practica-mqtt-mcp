#pragma once

#include <stdint.h>

// Ajustes exclusivos de la prueba local; no carga .env ni configuración MQTT.
namespace hardware_diagnostic {
namespace config {
constexpr int SERVO_PIN = 19;
constexpr int TRIGGER_PIN = 5;
constexpr int ECHO_PIN = 18;
constexpr unsigned long SERIAL_BAUD = 115200;

constexpr uint32_t MEASUREMENT_INTERVAL_MS = 500;
constexpr unsigned long ECHO_TIMEOUT_US = 30000;
constexpr float MIN_DISTANCE_CM = 2.0f;
constexpr float MAX_DISTANCE_CM = 400.0f;

constexpr int SERVO_MIN_ANGLE = 45;
constexpr int SERVO_CENTER_ANGLE = 90;
constexpr int SERVO_MAX_ANGLE = 135;
constexpr int SERVO_TARGETS[] = {
    SERVO_MIN_ANGLE, SERVO_CENTER_ANGLE, SERVO_MAX_ANGLE, SERVO_CENTER_ANGLE,
};
constexpr uint32_t SERVO_STEP_INTERVAL_MS = 25;
constexpr uint32_t SERVO_PAUSE_MS = 1500;
constexpr int SERVO_FREQUENCY_HZ = 50;
// Ventana conservadora: el recorrido diagnóstico usa solo su zona central.
constexpr int SERVO_MIN_PULSE_US = 1000;
constexpr int SERVO_MAX_PULSE_US = 2000;

static_assert(0 <= SERVO_MIN_ANGLE && SERVO_MIN_ANGLE < SERVO_CENTER_ANGLE &&
                  SERVO_CENTER_ANGLE < SERVO_MAX_ANGLE && SERVO_MAX_ANGLE <= 180,
              "Los objetivos del servo deben estar ordenados dentro de 0..180.");
static_assert(SERVO_STEP_INTERVAL_MS > 0 && SERVO_PAUSE_MS > 0,
              "El servo requiere pasos y pausas con duracion positiva.");
static_assert(MEASUREMENT_INTERVAL_MS >= 60,
              "Separar los disparos del HC-SR04 al menos 60 ms.");
}  // namespace config
}  // namespace hardware_diagnostic
