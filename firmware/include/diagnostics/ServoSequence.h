#pragma once

#include <stddef.h>
#include <stdint.h>

#include "DiagnosticConfig.h"

namespace hardware_diagnostic {

// Máquina de estados sin Arduino: el reloj lo entrega el llamador, no hay esperas.
class ServoSequence {
public:
    enum class State { Ready, Holding, Moving, Finished, Stopped };

    bool start(uint32_t now_ms) {
        if (state_ != State::Ready) {
            return false;
        }
        angle_ = config::SERVO_CENTER_ANGLE;
        last_event_ms_ = now_ms;
        state_ = State::Holding;
        return true;
    }

    // true indica una nueva consigna, como máximo 1 grado por llamada.
    bool update(uint32_t now_ms) {
        if (state_ == State::Holding) {
            if (elapsed(now_ms) >= config::SERVO_PAUSE_MS) {
                state_ = next_target_ == targetCount() ? State::Finished : State::Moving;
                last_event_ms_ = now_ms;
            }
            return false;
        }
        if (state_ != State::Moving || elapsed(now_ms) < config::SERVO_STEP_INTERVAL_MS) {
            return false;
        }

        // No recuperar pasos atrasados de golpe si otra tarea demoró el loop.
        last_event_ms_ = now_ms;
        const int target = config::SERVO_TARGETS[next_target_];
        angle_ += target > angle_ ? 1 : -1;
        if (angle_ == target) {
            ++next_target_;
            state_ = State::Holding;
        }
        return true;
    }

    void stop() {
        state_ = State::Stopped;
    }

    int angle() const {
        return angle_;
    }

    State state() const {
        return state_;
    }

private:
    static size_t targetCount() {
        return sizeof(config::SERVO_TARGETS) / sizeof(config::SERVO_TARGETS[0]);
    }

    uint32_t elapsed(uint32_t now_ms) const {
        // Resta sin signo: admite el desbordamiento de millis().
        return now_ms - last_event_ms_;
    }

    State state_ = State::Ready;
    int angle_ = config::SERVO_CENTER_ANGLE;
    size_t next_target_ = 0;
    uint32_t last_event_ms_ = 0;
};

}  // namespace hardware_diagnostic
