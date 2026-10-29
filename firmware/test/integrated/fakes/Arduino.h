#pragma once

#include <cassert>
#include <cstdint>
#include <string>
#include <utility>
#include <vector>

namespace integrated_test {
struct Publication {
    std::string topic, payload;
    int leds;
};
struct State {
    uint64_t now_us = 0;
    int levels[40] = {};
    int led_modes = 0, led_writes = 0, trigger_count = 0, echo_modes = 0;
    int starts = 0, updates = 0, ack_attempts = 0, distance_attempts = 0;
    int tasks = 0, task_core = -1, queue_resets = 0, overwrites = 0;
    bool connected = true, fail_ack = false, fail_queue = false, fail_task = false;
    bool in_worker = false;
    void (*echo_isr)(void*) = nullptr;
    void* echo_context = nullptr;
    void (*task)(void*) = nullptr;
    void* task_context = nullptr;
    void (*callback)(char*, uint8_t*, unsigned int) = nullptr;
    std::string client_id, subscription;
    std::vector<std::pair<std::string, std::string>> incoming;
    std::vector<Publication> publications;
};
inline State& state() { static State value; return value; }
inline void echoEdge(bool high) {
    auto& io = state();
    io.levels[18] = high ? 1 : 0;
    if (io.echo_isr != nullptr) io.echo_isr(io.echo_context);
}
}

constexpr int OUTPUT = 1, INPUT = 0, LOW = 0, HIGH = 1, CHANGE = 3;
#define ARDUINO_ISR_ATTR
struct portMUX_TYPE {};
#define portMUX_INITIALIZER_UNLOCKED {}
#define portENTER_CRITICAL(mux) static_cast<void>(mux)
#define portEXIT_CRITICAL(mux) static_cast<void>(mux)
#define portENTER_CRITICAL_ISR(mux) static_cast<void>(mux)
#define portEXIT_CRITICAL_ISR(mux) static_cast<void>(mux)

inline uint32_t millis() { return static_cast<uint32_t>(integrated_test::state().now_us / 1000); }
inline uint32_t micros() { return static_cast<uint32_t>(integrated_test::state().now_us); }
inline void delay(unsigned long ms) { integrated_test::state().now_us += ms * 1000; }
inline void delayMicroseconds(unsigned int us) {
    assert(us <= 10);  // El sensor integrado no debe esperar ECHO ni hacer pausas largas.
    integrated_test::state().now_us += us;
}
inline void pinMode(int pin, int mode) {
    auto& io = integrated_test::state();
    if (pin >= 25 && pin <= 27) {
        assert(mode == OUTPUT);
        ++io.led_modes;
    } else if (pin == 18) {
        assert(mode == INPUT);
        ++io.echo_modes;
    } else assert(pin == 5 && mode == OUTPUT);
}
inline void digitalWrite(int pin, int value) {
    assert(pin == 5 || (pin >= 25 && pin <= 27));
    assert(value == LOW || value == HIGH);
    auto& io = integrated_test::state();
    io.levels[pin] = value;
    if (pin == 5 && value == HIGH) ++io.trigger_count;
    if (pin >= 25) ++io.led_writes;
}
inline int digitalRead(int pin) {
    assert(pin == 18);
    return integrated_test::state().levels[pin];
}
inline void attachInterruptArg(int pin, void (*handler)(void*), void* context, int mode) {
    assert(pin == 18 && mode == CHANGE);
    integrated_test::state().echo_isr = handler;
    integrated_test::state().echo_context = context;
}
inline void detachInterrupt(int pin) {
    assert(pin == 18);
    integrated_test::state().echo_isr = nullptr;
}
inline unsigned long pulseIn(int, int, unsigned long) {
    assert(false && "No usar pulseIn en integrated.");
    return 0;
}
struct SerialDouble {
    void begin(int) {}
    void println(const char*) {}
    template <typename... Args> void printf(const char*, Args...) {}
};
static SerialDouble Serial;
