// Pruebas ejecutadas en el PC: no incluyen Arduino, ESP32Servo ni puertos serie.
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <vector>

#include "diagnostics/ServoSequence.h"

using hardware_diagnostic::ServoSequence;
namespace config = hardware_diagnostic::config;

static void verifyCompleteSequence(uint32_t start_ms) {
    ServoSequence sequence;
    assert(sequence.state() == ServoSequence::State::Ready);
    assert(!sequence.update(start_ms + 100000));
    assert(sequence.start(start_ms));
    assert(!sequence.start(start_ms + 1));

    int previous_angle = 90;
    int writes = 0;
    uint32_t last_write_ms = start_ms;
    std::vector<int> pauses;
    uint32_t hold_started_ms = start_ms;
    for (uint32_t offset = 0; offset < 30000; ++offset) {
        const uint32_t now_ms = start_ms + offset;
        const auto previous_state = sequence.state();
        const bool changed = sequence.update(now_ms);
        if (changed) {
            assert(std::abs(sequence.angle() - previous_angle) == 1);
            assert(sequence.angle() >= 45 && sequence.angle() <= 135);
            assert(static_cast<uint32_t>(now_ms - last_write_ms) >=
                   config::SERVO_STEP_INTERVAL_MS);
            previous_angle = sequence.angle();
            last_write_ms = now_ms;
            ++writes;
        }
        if (previous_state == ServoSequence::State::Holding &&
            sequence.state() != ServoSequence::State::Holding) {
            assert(static_cast<uint32_t>(now_ms - hold_started_ms) >=
                   config::SERVO_PAUSE_MS);
        }
        if (changed && sequence.state() == ServoSequence::State::Holding) {
            pauses.push_back(sequence.angle());
            hold_started_ms = now_ms;
        }
    }
    assert((pauses == std::vector<int>{45, 90, 135, 90}));
    assert(writes == 180);
    assert(sequence.state() == ServoSequence::State::Finished);
    assert(sequence.angle() == 90);
    assert(!sequence.start(start_ms + 30001));
    assert(!sequence.update(start_ms + 100000));
}

static void verifyStopAndLateTick() {
    ServoSequence sequence;
    assert(sequence.start(0));
    assert(!sequence.update(config::SERVO_PAUSE_MS));
    // Una demora larga del loop solo produce un paso; no salta hasta 45 grados.
    assert(sequence.update(10000));
    assert(sequence.angle() == 89);
    assert(!sequence.update(10000));
    sequence.stop();
    assert(!sequence.update(20000));
    assert(sequence.angle() == 89);
    assert(sequence.state() == ServoSequence::State::Stopped);
    assert(!sequence.start(20001));

    ServoSequence disarmed;
    disarmed.stop();
    assert(!disarmed.start(0));
    assert(!disarmed.update(100000));
}

int main() {
    verifyCompleteSequence(0);
    verifyCompleteSequence(UINT32_MAX - 500);  // Cruza el desbordamiento de millis().
    verifyStopAndLateTick();
    std::cout << "ServoSequence: limites, pausas, ciclo unico, parada y reloj OK.\n";
    return 0;
}
