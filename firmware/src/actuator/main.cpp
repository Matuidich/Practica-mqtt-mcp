#include <Arduino.h>

#include "distributed/LedController.h"
#include "distributed/LedSettings.h"
#include "distributed/WifiMqttConnection.h"

namespace {
class ActuatorApplication {
public:
    ActuatorApplication()
        : ack_retry_(project_config::MQTT_RECONNECT_MIN_DELAY_MS,
                     project_config::MQTT_RECONNECT_MAX_DELAY_MS) {}

    void begin(iot_firmware::WifiMqttConnection::Callback callback) {
        Serial.begin(115200);
        Serial.println("ESP32 actuator: LEDs rojo, amarillo y verde.");
        if (led_config::WIRING_CONFIRMED) {
            const int pins[] = {led_config::RED_PIN, led_config::YELLOW_PIN, led_config::GREEN_PIN};
            for (int pin : pins) {
                pinMode(pin, OUTPUT);
                digitalWrite(pin, LOW);
            }
        } else {
            Serial.println("Salidas bloqueadas: LED_WIRING_CONFIRMED=false.");
        }
        network_.begin(project_config::MQTT_CLIENT_ID_ACTUATOR,
                       project_config::MQTT_TOPIC_LED_COMMAND, callback);
    }

    void onMessage(char* topic, uint8_t* payload, unsigned int length) {
        if (std::strcmp(topic, project_config::MQTT_TOPIC_LED_COMMAND) != 0) return;
        iot_firmware::LedCommand command;
        if (!parser_.parse(payload, length, command)) {
            Serial.println("Orden LED rechazada: JSON, colores, booleanos o command_id invalidos.");
            return;
        }
        if (!led_config::WIRING_CONFIRMED) {
            Serial.println("Orden LED rechazada: verificar primero el cableado.");
            return;
        }
        const auto decision = controller_.accept(command, millis());
        if (decision == iot_firmware::LedController::Decision::Applied) {
            const uint8_t values = controller_.values();
            digitalWrite(led_config::RED_PIN, values & 1 ? HIGH : LOW);
            digitalWrite(led_config::YELLOW_PIN, values & 2 ? HIGH : LOW);
            digitalWrite(led_config::GREEN_PIN, values & 4 ? HIGH : LOW);
            ack_retry_.reset();
        } else if (decision != iot_firmware::LedController::Decision::Replay) {
            Serial.println("Orden LED sin nuevo cambio: duplicada, conflictiva u ocupada.");
        }
    }

    void update() {
        network_.update();
        const uint32_t now_ms = millis();
        if (!controller_.pending() || !network_.connected() || !ack_retry_.ready(now_ms)) return;
        char payload[320];
        const size_t size = iot_firmware::encodeLedState(payload, sizeof(payload),
            controller_.values(), controller_.commandId(), device_config::ACTUATOR_DEVICE_ID,
            controller_.appliedAt());
        if (size > 0 && network_.publish(project_config::MQTT_TOPIC_LED_STATE, payload, size)) {
            controller_.confirmationSent();
            ack_retry_.reset();
            Serial.println("Confirmacion LED applied enviada; QoS 0 no garantiza entrega.");
        } else {
            ack_retry_.failed(millis());
        }
    }

private:
    iot_firmware::WifiMqttConnection network_;
    iot_firmware::LedCommandParser parser_;
    iot_firmware::LedController controller_;
    iot_firmware::Backoff ack_retry_;
};

ActuatorApplication application;
void onCommand(char* topic, uint8_t* payload, unsigned int length) {
    application.onMessage(topic, payload, length);
}
}  // namespace

void setup() { application.begin(onCommand); }
void loop() {
    application.update();
    delay(1);
}
