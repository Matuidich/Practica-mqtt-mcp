#pragma once

#include <Arduino.h>

namespace iot_firmware {

class Hcsr04 {
public:
    Hcsr04(int trigger_pin, int echo_pin, unsigned long timeout_us)
        : trigger_pin_(trigger_pin), echo_pin_(echo_pin), timeout_us_(timeout_us) {}

    void begin() {
        pinMode(trigger_pin_, OUTPUT);
        digitalWrite(trigger_pin_, LOW);
        pinMode(echo_pin_, INPUT);
    }

    bool read(float& centimeters) {
        digitalWrite(trigger_pin_, LOW);
        delayMicroseconds(2);
        digitalWrite(trigger_pin_, HIGH);
        delayMicroseconds(10);
        digitalWrite(trigger_pin_, LOW);
        const unsigned long echo_us = pulseIn(echo_pin_, HIGH, timeout_us_);
        if (echo_us == 0) return false;
        const float measured = static_cast<float>(echo_us) / 58.0f;
        if (measured < 2.0f || measured > 400.0f) return false;
        centimeters = measured;
        return true;
    }

private:
    int trigger_pin_, echo_pin_;
    unsigned long timeout_us_;
};
}  // namespace iot_firmware
