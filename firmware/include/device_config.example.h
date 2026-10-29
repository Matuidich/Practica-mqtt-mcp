#pragma once

// Añadir también estas opciones a una copia local antigua, sin reemplazar Wi-Fi.
// Solo habilitar tras comprobar físicamente resistencias, polaridad y GND.
#define LED_WIRING_CONFIRMED false
#define LED_RED_PIN 25
#define LED_YELLOW_PIN 26
#define LED_GREEN_PIN 27

// Copiar manualmente a device_config.local.h y editar solo esa copia ignorada.
// Con SSID vacío se puede compilar, pero no se intenta conectar a Wi-Fi.
namespace device_config {
constexpr char WIFI_SSID[] = "";
constexpr char WIFI_PASSWORD[] = "";

constexpr int SENSOR_TRIGGER_PIN = 5;
constexpr int SENSOR_ECHO_PIN = 18;  // ECHO mediante divisor de tensión.
constexpr int ACTUATOR_SERVO_PIN = 25;  // Solo referencia histórica SG90.
constexpr bool ACTUATOR_WIRING_CONFIRMED = false;

constexpr char SENSOR_DEVICE_ID[] = "sensor-01";
constexpr char ACTUATOR_DEVICE_ID[] = "actuator-01";
constexpr unsigned long SENSOR_ECHO_TIMEOUT_US = 30000;
constexpr unsigned long WIFI_CONNECT_TIMEOUT_MS = 10000;
constexpr unsigned long TCP_CONNECT_TIMEOUT_MS = 1500;
constexpr unsigned int MQTT_SOCKET_TIMEOUT_S = 2;
constexpr unsigned long SERVO_STEP_INTERVAL_MS = 25;
constexpr unsigned long SERVO_SETTLE_MS = 500;
constexpr int SERVO_MIN_PULSE_US = 1000;
constexpr int SERVO_MAX_PULSE_US = 2000;
}  // namespace device_config
