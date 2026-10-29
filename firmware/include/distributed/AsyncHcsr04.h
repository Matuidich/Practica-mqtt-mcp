#pragma once

#include <Arduino.h>

namespace iot_firmware {

// Captura los flancos ECHO en una ISR. Solo el pulso TRIG de 12 us usa espera.
class AsyncHcsr04 {
public:
    enum class Result { Pending, Valid, Invalid };

    AsyncHcsr04(int trigger_pin, int echo_pin, uint32_t timeout_us)
        : trigger_pin_(trigger_pin), echo_pin_(echo_pin), timeout_us_(timeout_us) {}

    void begin() {
        pinMode(trigger_pin_, OUTPUT);
        digitalWrite(trigger_pin_, LOW);
        pinMode(echo_pin_, INPUT);
        attachInterruptArg(echo_pin_, echoInterrupt, this, CHANGE);
    }

    void end() {
        detachInterrupt(echo_pin_);
        waiting_ = false;
        portENTER_CRITICAL(&mux_);
        capturing_ = false;
        portEXIT_CRITICAL(&mux_);
    }

    bool start() {
        if (waiting_) return false;
        portENTER_CRITICAL(&mux_);
        started_us_ = micros();
        risen_ = false;
        ready_ = false;
        width_us_ = 0;
        capturing_ = true;
        portEXIT_CRITICAL(&mux_);
        waiting_ = true;
        digitalWrite(trigger_pin_, LOW);
        delayMicroseconds(2);
        digitalWrite(trigger_pin_, HIGH);
        delayMicroseconds(10);
        digitalWrite(trigger_pin_, LOW);
        return true;
    }

    Result poll(float& centimeters) {
        if (!waiting_) return Result::Pending;
        const uint32_t now_us = micros();
        portENTER_CRITICAL(&mux_);
        const bool ready = ready_;
        const bool expired = static_cast<uint32_t>(now_us - started_us_) >= timeout_us_;
        const uint32_t width = width_us_;
        if (ready || expired) capturing_ = false;
        portEXIT_CRITICAL(&mux_);
        if (!ready && !expired) return Result::Pending;
        waiting_ = false;
        const float measured = static_cast<float>(width) / 58.0f;
        if (!ready || width == 0 || measured < 2.0f || measured > 400.0f)
            return Result::Invalid;
        centimeters = measured;
        return Result::Valid;
    }

    bool busy() const { return waiting_; }

private:
    static void ARDUINO_ISR_ATTR echoInterrupt(void* context) {
        auto* sensor = static_cast<AsyncHcsr04*>(context);
        const uint32_t now_us = micros();
        const bool high = digitalRead(sensor->echo_pin_) == HIGH;
        portENTER_CRITICAL_ISR(&sensor->mux_);
        if (sensor->capturing_) {
            if (static_cast<uint32_t>(now_us - sensor->started_us_) >= sensor->timeout_us_) {
                sensor->width_us_ = 0;
                sensor->ready_ = true;
                sensor->capturing_ = false;
            } else if (high && !sensor->risen_) {
                sensor->rise_us_ = now_us;
                sensor->risen_ = true;
            } else if (!high && sensor->risen_) {
                sensor->width_us_ = now_us - sensor->rise_us_;
                sensor->ready_ = true;
                sensor->capturing_ = false;
            }
        }
        portEXIT_CRITICAL_ISR(&sensor->mux_);
    }

    const int trigger_pin_, echo_pin_;
    const uint32_t timeout_us_;
    portMUX_TYPE mux_ = portMUX_INITIALIZER_UNLOCKED;
    volatile uint32_t started_us_ = 0, rise_us_ = 0, width_us_ = 0;
    volatile bool capturing_ = false, risen_ = false, ready_ = false;
    bool waiting_ = false;
};
}  // namespace iot_firmware
