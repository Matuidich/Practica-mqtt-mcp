#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/task.h>

#include "distributed/AsyncHcsr04.h"
#include "distributed/LedController.h"
#include "distributed/LedSettings.h"
#include "distributed/WifiMqttConnection.h"

static_assert(device_config::SENSOR_TRIGGER_PIN != device_config::SENSOR_ECHO_PIN,
              "TRIG y ECHO requieren GPIO distintos.");
static_assert(led_config::RED_PIN != device_config::SENSOR_TRIGGER_PIN &&
              led_config::RED_PIN != device_config::SENSOR_ECHO_PIN &&
              led_config::YELLOW_PIN != device_config::SENSOR_TRIGGER_PIN &&
              led_config::YELLOW_PIN != device_config::SENSOR_ECHO_PIN &&
              led_config::GREEN_PIN != device_config::SENSOR_TRIGGER_PIN &&
              led_config::GREEN_PIN != device_config::SENSOR_ECHO_PIN,
              "Los GPIO LED no pueden coincidir con TRIG o ECHO.");

namespace {
struct DistanceSample {
    float centimeters;
    uint32_t uptime_ms;
};

class IntegratedApplication {
public:
    IntegratedApplication()
        : sensor_(device_config::SENSOR_TRIGGER_PIN, device_config::SENSOR_ECHO_PIN,
                  device_config::SENSOR_ECHO_TIMEOUT_US),
          ack_retry_(project_config::MQTT_RECONNECT_MIN_DELAY_MS,
                     project_config::MQTT_RECONNECT_MAX_DELAY_MS) {}

    void begin(iot_firmware::WifiMqttConnection::Callback callback) {
        Serial.begin(115200);
        Serial.println("ESP32 integrated: HC-SR04 y LEDs rojo, amarillo y verde.");
        if (led_config::WIRING_CONFIRMED) {
            const int pins[] = {led_config::RED_PIN, led_config::YELLOW_PIN, led_config::GREEN_PIN};
            for (int pin : pins) {
                pinMode(pin, OUTPUT);
                digitalWrite(pin, LOW);
            }
        } else {
            Serial.println("Salidas bloqueadas: LED_WIRING_CONFIRMED=false.");
        }
        callback_ = callback;
        distance_queue_ = xQueueCreate(1, sizeof(DistanceSample));
        if (distance_queue_ == nullptr) {
            Serial.println("Error: no hay memoria para la cola; MQTT no se inicia.");
            return;
        }
        sensor_.begin();
        last_measurement_ms_ = millis();
        // PubSubClient es síncrono: solo esta tarea accede al cliente y sus callbacks.
        if (xTaskCreatePinnedToCore(networkTask, "sis234-mqtt", 8192, this, 1, nullptr, 0) != pdPASS) {
            sensor_.end();
            vQueueDelete(distance_queue_);
            distance_queue_ = nullptr;
            Serial.println("Error: no se pudo iniciar la tarea MQTT; LEDs quedan apagados.");
        }
    }

    // Solo loop() llama a este método. No espera ECHO ni accede a MQTT.
    void updateSensor() {
        if (distance_queue_ == nullptr) return;
        float centimeters = 0;
        const auto result = sensor_.poll(centimeters);
        if (result == iot_firmware::AsyncHcsr04::Result::Valid) {
            const DistanceSample sample{centimeters, millis()};
            xQueueOverwrite(distance_queue_, &sample);  // Solo la lectura más reciente.
            Serial.printf("HC-SR04 %.1f cm; lectura reciente disponible.\n", centimeters);
        } else if (result == iot_firmware::AsyncHcsr04::Result::Invalid) {
            Serial.println("HC-SR04: sin eco o fuera de rango; lectura descartada.");
        }
        const uint32_t now_ms = millis();
        if (!sensor_.busy() && static_cast<uint32_t>(now_ms - last_measurement_ms_) >=
                project_config::DISTANCE_PUBLISH_INTERVAL_MS) {
            last_measurement_ms_ = now_ms;
            sensor_.start();
        }
    }

    // startNetwork, updateNetwork y onMessage pertenecen a la tarea MQTT.
    void startNetwork() {
        network_.begin(project_config::MQTT_CLIENT_ID,
                       project_config::MQTT_TOPIC_LED_COMMAND, callback_);
    }

    void onMessage(char* topic, uint8_t* payload, unsigned int length) {
        if (std::strcmp(topic, project_config::MQTT_TOPIC_LED_COMMAND) != 0) return;
        iot_firmware::LedCommand command;
        if (!parser_.parse(payload, length, command)) {
            Serial.println("Orden LED rechazada: JSON o command_id invalidos.");
            return;
        }
        if (!led_config::WIRING_CONFIRMED) {
            Serial.println("Orden LED rechazada: verificar primero el cableado.");
            return;
        }
        const auto decision = leds_.accept(command, millis());
        if (decision == iot_firmware::LedController::Decision::Applied) {
            const uint8_t values = leds_.values();
            digitalWrite(led_config::RED_PIN, values & 1 ? HIGH : LOW);
            digitalWrite(led_config::YELLOW_PIN, values & 2 ? HIGH : LOW);
            digitalWrite(led_config::GREEN_PIN, values & 4 ? HIGH : LOW);
            ack_retry_.reset();
        } else if (decision != iot_firmware::LedController::Decision::Replay) {
            Serial.println("Orden LED sin nuevo cambio: duplicada, conflictiva u ocupada.");
        }
    }

    void updateNetwork() {
        if (distance_queue_ == nullptr) return;
        network_.update();
        const bool connected = network_.connected();
        // Descartar muestras de la desconexión: esperar una medición posterior al reconectar.
        if (!connected || !was_connected_) xQueueReset(distance_queue_);
        was_connected_ = connected;
        if (!connected) return;
        const uint32_t now_ms = millis();
        if (leds_.pending() && ack_retry_.ready(now_ms)) {
            char payload[320];
            const size_t size = iot_firmware::encodeLedState(payload, sizeof(payload),
                leds_.values(), leds_.commandId(), device_config::ACTUATOR_DEVICE_ID,
                leds_.appliedAt());
            if (size > 0 && network_.publish(project_config::MQTT_TOPIC_LED_STATE, payload, size)) {
                leds_.confirmationSent();
                ack_retry_.reset();
                Serial.println("Confirmacion LED applied enviada; QoS 0 no garantiza entrega.");
            } else {
                ack_retry_.failed(millis());
            }
        }
        DistanceSample sample;
        if (xQueueReceive(distance_queue_, &sample, 0) == pdTRUE &&
            static_cast<uint32_t>(millis() - sample.uptime_ms) <
                project_config::DISTANCE_PUBLISH_INTERVAL_MS) {
            char payload[256];
            const size_t size = iot_firmware::encodeDistance(payload, sizeof(payload),
                sample.centimeters, device_config::SENSOR_DEVICE_ID, sample.uptime_ms);
            const bool sent = size > 0 &&
                network_.publish(project_config::MQTT_TOPIC_DISTANCE, payload, size);
            Serial.printf("Distancia %.1f cm; MQTT %s.\n", sample.centimeters,
                          sent ? "enviado a TCP" : "lectura descartada");
        }
    }

private:
    static void networkTask(void* context) {
        auto* application = static_cast<IntegratedApplication*>(context);
        application->startNetwork();
        for (;;) {
            application->updateNetwork();
            vTaskDelay(1);  // Ceder siempre: no hay reintentos sin pausa.
        }
    }

    iot_firmware::AsyncHcsr04 sensor_;
    iot_firmware::WifiMqttConnection network_;
    iot_firmware::LedCommandParser parser_;
    iot_firmware::LedController leds_;
    iot_firmware::Backoff ack_retry_;
    QueueHandle_t distance_queue_ = nullptr;
    iot_firmware::WifiMqttConnection::Callback callback_ = nullptr;
    uint32_t last_measurement_ms_ = 0;
    bool was_connected_ = false;
};

IntegratedApplication application;
void onCommand(char* topic, uint8_t* payload, unsigned int length) {
    application.onMessage(topic, payload, length);
}
}  // namespace

void setup() { application.begin(onCommand); }
void loop() {
    application.updateSensor();
    delay(1);
}
