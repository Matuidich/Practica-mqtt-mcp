#pragma once

#include <Arduino.h>

#include "DiagnosticConfig.h"

namespace hardware_diagnostic {

class UltrasonicSensor {
public:
    enum class Status { Valid, NoEcho, OutOfRange };

    struct Measurement {
        Status status;
        unsigned long echo_us;
        float distance_cm;
    };

    void begin() {
        pinMode(config::TRIGGER_PIN, OUTPUT);
        digitalWrite(config::TRIGGER_PIN, LOW);
        pinMode(config::ECHO_PIN, INPUT);
    }

    Measurement measure() {
        digitalWrite(config::TRIGGER_PIN, LOW);
        delayMicroseconds(2);
        digitalWrite(config::TRIGGER_PIN, HIGH);
        delayMicroseconds(10);
        digitalWrite(config::TRIGGER_PIN, LOW);

        const unsigned long echo_us = pulseIn(
            config::ECHO_PIN, HIGH, config::ECHO_TIMEOUT_US
        );
        if (echo_us == 0) {
            return {Status::NoEcho, 0, 0.0f};
        }
        const float distance_cm = static_cast<float>(echo_us) / 58.0f;
        const bool in_range = distance_cm >= config::MIN_DISTANCE_CM &&
                              distance_cm <= config::MAX_DISTANCE_CM;
        return {in_range ? Status::Valid : Status::OutOfRange, echo_us, distance_cm};
    }
};

}  // namespace hardware_diagnostic
