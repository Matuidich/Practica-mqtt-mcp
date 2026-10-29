#pragma once

// Valores ficticios: las pruebas no incluyen .env ni credenciales locales.
#ifndef TEST_ACTUATOR_WIRING_CONFIRMED
#error "La prueba debe declarar si el cableado esta confirmado."
#endif

namespace project_config {
constexpr int SERVO_MIN_ANGLE = 0;
constexpr int SERVO_MAX_ANGLE = 180;
constexpr unsigned long MQTT_RECONNECT_MIN_DELAY_MS = 1000;
constexpr unsigned long MQTT_RECONNECT_MAX_DELAY_MS = 32000;
constexpr char MQTT_CLIENT_ID_ACTUATOR[] = "offline-actuator";
constexpr char MQTT_TOPIC_SERVO_COMMAND[] = "offline/commands/servo";
constexpr char MQTT_TOPIC_SERVO_STATE[] = "offline/state/servo";
}  // namespace project_config

namespace device_config {
constexpr int ACTUATOR_SERVO_PIN = 25;
constexpr bool ACTUATOR_WIRING_CONFIRMED = TEST_ACTUATOR_WIRING_CONFIRMED != 0;
constexpr unsigned long SERVO_STEP_INTERVAL_MS = 25;
constexpr unsigned long SERVO_SETTLE_MS = 500;
constexpr int SERVO_MIN_PULSE_US = 1000;
constexpr int SERVO_MAX_PULSE_US = 2000;
constexpr char ACTUATOR_DEVICE_ID[] = "offline-actuator";
}  // namespace device_config
