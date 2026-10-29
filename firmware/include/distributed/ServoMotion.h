#pragma once

#include <stdint.h>

namespace iot_firmware {

// Rampa de consignas, sin GPIO ni dependencia de Arduino.
class ServoMotion {
public:
    ServoMotion(int minimum, int maximum, uint32_t step_ms, uint32_t settle_ms)
        : minimum_(minimum), maximum_(maximum), step_ms_(step_ms), settle_ms_(settle_ms),
          angle_(90 < minimum ? minimum : (90 > maximum ? maximum : 90)) {}

    bool start(int target, uint32_t now_ms) {
        if (busy() || target < minimum_ || target > maximum_) return false;
        target_ = target;
        last_ = now_ms;
        state_ = target_ == angle_ ? State::Settling : State::Moving;
        return true;
    }

    bool update(uint32_t now_ms) {
        const uint32_t elapsed = now_ms - last_;
        if (state_ == State::Moving && elapsed >= step_ms_) {
            angle_ += target_ > angle_ ? 1 : -1;
            last_ = now_ms;
            if (angle_ == target_) state_ = State::Settling;
            return true;
        }
        if (state_ == State::Settling && elapsed >= settle_ms_) state_ = State::Complete;
        return false;
    }

    bool busy() const { return state_ == State::Moving || state_ == State::Settling; }
    bool complete() const { return state_ == State::Complete; }
    int angle() const { return angle_; }

private:
    enum class State { Idle, Moving, Settling, Complete };
    int minimum_, maximum_;
    uint32_t step_ms_, settle_ms_;
    int angle_, target_ = 90;
    uint32_t last_ = 0;
    State state_ = State::Idle;
};
}  // namespace iot_firmware
