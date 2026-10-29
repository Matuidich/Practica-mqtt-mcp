#pragma once
#include <cassert>
#include <cstdint>
#include <string>
#include <vector>

namespace led_test {
struct State {
    uint32_t now_ms = 0;
    int pin_modes = 0, writes = 0, levels = 0, attempts = 0;
    bool connected = true, publish_succeeds = true;
    std::vector<std::string> publications;
    std::string subscription, client_id;
};
inline State& state() { static State value; return value; }
}
constexpr int OUTPUT = 1, LOW = 0, HIGH = 1;
inline uint32_t millis() { return led_test::state().now_ms; }
inline void delay(unsigned long ms) { led_test::state().now_ms += ms; }
inline void pinMode(int pin, int mode) {
    assert(pin >= 25 && pin <= 27 && mode == OUTPUT);
    ++led_test::state().pin_modes;
}
inline void digitalWrite(int pin, int value) {
    assert(pin >= 25 && pin <= 27 && (value == LOW || value == HIGH));
    auto& io = led_test::state();
    ++io.writes;
    const int bit = 1 << (pin - 25);
    io.levels = (io.levels & ~bit) | (value == HIGH ? bit : 0);
}
struct SerialDouble {
    void begin(int) {}
    void println(const char*) {}
    template <typename... Args> void printf(const char*, Args...) {}
};
static SerialDouble Serial;
