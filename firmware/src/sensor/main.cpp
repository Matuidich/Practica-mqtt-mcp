#include <Arduino.h>

#include "distributed/DeviceSettings.h"
#include "distributed/Hcsr04.h"
#include "distributed/WifiMqttConnection.h"
#include "distributed/WireMessages.h"

namespace {
class SensorApplication {
public:
    SensorApplication()
        : sensor_(device_config::SENSOR_TRIGGER_PIN, device_config::SENSOR_ECHO_PIN,
                  device_config::SENSOR_ECHO_TIMEOUT_US) {}

    void begin() {
        Serial.begin(115200);
        Serial.println("ESP32 sensor: HC-SR04, sin control de servo.");
        sensor_.begin();
        network_.begin(project_config::MQTT_CLIENT_ID_SENSOR);
        last_measurement_ms_ = millis();
    }

    void update() {
        network_.update();
        const uint32_t now_ms = millis();
        if (static_cast<uint32_t>(now_ms - last_measurement_ms_) <
            project_config::DISTANCE_PUBLISH_INTERVAL_MS) return;
        last_measurement_ms_ = now_ms;
        float centimeters = 0;
        if (!sensor_.read(centimeters)) {
            Serial.println("HC-SR04: sin eco o fuera de rango; no se publica un cero.");
            return;
        }
        char payload[256];
        const size_t size = iot_firmware::encodeDistance(
            payload, sizeof(payload), centimeters, device_config::SENSOR_DEVICE_ID, millis());
        if (size == 0) {
            Serial.println("Error al codificar la distancia.");
            return;
        }
        const bool sent = network_.publish(project_config::MQTT_TOPIC_DISTANCE, payload, size);
        Serial.printf("Distancia %.1f cm; MQTT %s.\n", centimeters,
                      sent ? "enviado a TCP" : "no disponible, lectura descartada");
        // No guardar una cola de mediciones antiguas cuando no hay conexión.
    }

private:
    iot_firmware::Hcsr04 sensor_;
    iot_firmware::WifiMqttConnection network_;
    uint32_t last_measurement_ms_ = 0;
};

SensorApplication application;
}  // namespace

void setup() { application.begin(); }
void loop() {
    application.update();
    delay(1);
}
