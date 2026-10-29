#pragma once

#include <cassert>
#include <cstdint>
#include <string>
#include <vector>

// Dobles exclusivos del ejecutable de PC: nunca incluyen Arduino ni abren puertos.
namespace actuator_test {
struct ServoWrite {
    uint32_t at_ms;
    int angle;
};

struct Publication {
    std::string topic, payload;
    bool pwm_active;
    int angle;
};

struct State {
    uint32_t now_ms = 0, last_publish_attempt_ms = 0;
    bool attached = false, attach_succeeds = true;
    bool connected = true, publish_succeeds = true;
    int attach_calls = 0, detach_calls = 0, frequency_calls = 0;
    int pin_mode_calls = 0, low_calls = 0, publish_attempts = 0;
    int pin = -1, frequency_hz = 0, minimum_us = 0, maximum_us = 0;
    int angle = -1;
    std::vector<ServoWrite> writes;
    std::vector<Publication> publications;
};

inline State& state() {
    static State instance;
    return instance;
}
}  // namespace actuator_test

constexpr int OUTPUT = 1;
constexpr int LOW = 0;
inline uint32_t millis() { return actuator_test::state().now_ms; }
inline void delay(unsigned long duration_ms) { actuator_test::state().now_ms += duration_ms; }
inline void pinMode(int pin, int mode) {
    assert(pin == 25 && mode == OUTPUT);
    ++actuator_test::state().pin_mode_calls;
}
inline void digitalWrite(int pin, int value) {
    assert(pin == 25 && value == LOW);
    ++actuator_test::state().low_calls;
}

struct SerialDouble {
    void begin(int) {}
    void println(const char*) {}
    template <typename... Args> void printf(const char*, Args...) {}
};
static SerialDouble Serial;
