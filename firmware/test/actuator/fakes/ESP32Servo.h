#pragma once

#include "Arduino.h"

class Servo {
public:
    void setPeriodHertz(int frequency) {
        auto& io = actuator_test::state();
        ++io.frequency_calls;
        io.frequency_hz = frequency;
    }

    int attach(int pin, int minimum_us, int maximum_us) {
        auto& io = actuator_test::state();
        ++io.attach_calls;
        io.pin = pin;
        io.minimum_us = minimum_us;
        io.maximum_us = maximum_us;
        io.attached = io.attach_succeeds;
        return io.attached ? 0 : -1;
    }

    bool attached() const { return actuator_test::state().attached; }
    void detach() {
        ++actuator_test::state().detach_calls;
        actuator_test::state().attached = false;
    }

    void write(int angle) {
        auto& io = actuator_test::state();
        assert(io.attached && angle >= 0 && angle <= 180);
        io.angle = angle;
        io.writes.push_back({io.now_ms, angle});
    }
};
