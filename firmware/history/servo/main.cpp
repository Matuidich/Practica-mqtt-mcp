#include <Arduino.h>
#include <ESP32Servo.h>

#include "distributed/CommandTracker.h"
#include "distributed/DeviceSettings.h"
#include "distributed/ServoMotion.h"
#include "distributed/WifiMqttConnection.h"

namespace {
class ActuatorApplication {
public:
    ActuatorApplication()
        : motion_(project_config::SERVO_MIN_ANGLE, project_config::SERVO_MAX_ANGLE,
                  device_config::SERVO_STEP_INTERVAL_MS, device_config::SERVO_SETTLE_MS),
          ack_retry_(project_config::MQTT_RECONNECT_MIN_DELAY_MS,
                     project_config::MQTT_RECONNECT_MAX_DELAY_MS) {}

    void begin(iot_firmware::WifiMqttConnection::Callback callback) {
        Serial.begin(115200);
        Serial.println("ESP32 actuator: SG90 GPIO 25, pendiente de confirmar cableado.");
        if (device_config::ACTUATOR_WIRING_CONFIRMED) {
            disableServo();
        } else {
            Serial.println("Movimiento bloqueado: ACTUATOR_WIRING_CONFIRMED=false.");
        }
        network_.begin(project_config::MQTT_CLIENT_ID_ACTUATOR,
                       project_config::MQTT_TOPIC_SERVO_COMMAND, callback);
    }

    void onMessage(char* topic, uint8_t* payload, unsigned int length) {
        if (std::strcmp(topic, project_config::MQTT_TOPIC_SERVO_COMMAND) != 0) return;
        iot_firmware::ServoCommand command;
        if (!parser_.parse(payload, length, project_config::SERVO_MIN_ANGLE,
                           project_config::SERVO_MAX_ANGLE, command)) {
            Serial.println("Orden rechazada: JSON, campos, identificador o angulo invalidos.");
            return;
        }
        if (!device_config::ACTUATOR_WIRING_CONFIRMED) {
            Serial.println("Orden rechazada: confirmar primero el cableado GPIO 25.");
            return;
        }
        const auto decision = tracker_.accept(command);
        if (decision != iot_firmware::CommandTracker::Decision::Start) {
            Serial.println("Orden sin nuevo movimiento: duplicada, pendiente u ocupada.");
            return;
        }
        if (!servo_.attached()) {
            servo_.setPeriodHertz(50);
            servo_.attach(device_config::ACTUATOR_SERVO_PIN,
                          device_config::SERVO_MIN_PULSE_US, device_config::SERVO_MAX_PULSE_US);
        }
        if (!servo_.attached()) {
            tracker_.cancelActive();
            disableServo();
            Serial.println("No se pudo iniciar PWM; no se confirma la orden.");
            return;
        }
        // Posición asumida, no medida. El primer centrado puede mover el SG90.
        servo_.write(motion_.angle());
        motion_.start(command.angle, millis());
        Serial.printf("Orden %s: consigna objetivo %d.\n", command.command_id, command.angle);
    }

    void update() {
        network_.update();
        const uint32_t now_ms = millis();
        if (tracker_.active()) {
            if (motion_.update(now_ms)) servo_.write(motion_.angle());
            if (motion_.complete()) {
                // LEDC mantiene la última consigna PWM, también después de applied.
                tracker_.applied(now_ms);
                ack_retry_.reset();
            }
        }
        if (!tracker_.pending() || !network_.connected() || !ack_retry_.ready(now_ms)) return;
        char payload[256];
        const size_t size = iot_firmware::encodeState(
            payload, sizeof(payload), tracker_.confirmation(), device_config::ACTUATOR_DEVICE_ID,
            tracker_.appliedAt(), project_config::SERVO_MIN_ANGLE, project_config::SERVO_MAX_ANGLE);
        if (size > 0 && network_.publish(project_config::MQTT_TOPIC_SERVO_STATE, payload, size)) {
            tracker_.confirmationSent();
            ack_retry_.reset();
            Serial.println("Confirmacion applied enviada a TCP; QoS 0 no garantiza entrega.");
        } else {
            ack_retry_.failed(millis());
        }
    }

private:
    void disableServo() {
        if (servo_.attached()) servo_.detach();
        pinMode(device_config::ACTUATOR_SERVO_PIN, OUTPUT);
        digitalWrite(device_config::ACTUATOR_SERVO_PIN, LOW);
    }

    iot_firmware::WifiMqttConnection network_;
    iot_firmware::CommandParser parser_;
    iot_firmware::CommandTracker tracker_;
    iot_firmware::ServoMotion motion_;
    iot_firmware::Backoff ack_retry_;
    Servo servo_;
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
