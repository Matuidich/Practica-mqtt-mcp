// Ejecutable de pruebas en el PC. No incluye Arduino, Wi-Fi, MQTT ni Servo.
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

#include "distributed/Backoff.h"
#include "distributed/CommandTracker.h"
#include "distributed/ServoMotion.h"

using namespace iot_firmware;

static ServoCommand command(int angle, const char* id) {
    ServoCommand result;
    result.angle = angle;
    std::strcpy(result.command_id, id);
    return result;
}

static void testBackoff() {
    Backoff retry(1000, 32000);
    assert(retry.ready(0));
    uint32_t time = 0;
    for (uint32_t expected : {1000U, 2000U, 4000U, 8000U, 16000U, 32000U, 32000U}) {
        retry.failed(time);
        assert(retry.delayMs() == expected);
        assert(!retry.ready(time + expected - 1));
        assert(retry.ready(time + expected));
        time += expected;
    }
    retry.reset();
    assert(retry.ready(time));
    retry.failed(UINT32_MAX - 500);
    assert(retry.delayMs() == 1000);
    assert(!retry.ready(498));
    assert(retry.ready(499));
}

static void testMotion() {
    ServoMotion motion(15, 165, 25, 500);
    assert(!motion.update(100000));  // Sin orden no hay barrido automático.
    assert(!motion.start(14, 0));
    assert(!motion.start(166, 0));
    assert(motion.start(165, UINT32_MAX - 100));
    assert(!motion.start(45, 0));
    int last = 90, steps = 0;
    for (uint32_t elapsed = 0; elapsed < 4000; ++elapsed) {
        if (motion.update(UINT32_MAX - 100 + elapsed)) {
            assert(motion.angle() == last + 1);
            assert(motion.angle() <= 165);
            last = motion.angle();
            ++steps;
        }
    }
    assert(steps == 75 && motion.complete());
    assert(motion.start(15, 5000));
    assert(motion.update(15000));  // No recuperar pasos atrasados de golpe.
    assert(motion.angle() == 164);
    assert(!motion.update(15000));
    for (uint32_t time = 15001; time < 20000; ++time) motion.update(time);
    assert(motion.complete() && motion.angle() == 15);
    assert(motion.start(15, 20000));
    assert(!motion.update(20499) && !motion.complete());
    assert(!motion.update(20500) && motion.complete());
}

static void testCommandTracking() {
    CommandTracker tracker;
    const auto a = command(45, "a-1");
    const auto b = command(135, "b-1");
    using Decision = CommandTracker::Decision;
    assert(tracker.accept(a) == Decision::Start);
    assert(tracker.accept(a) == Decision::Duplicate);
    assert(tracker.accept(command(46, "a-1")) == Decision::ConflictingId);
    assert(tracker.accept(b) == Decision::Busy);
    tracker.applied(12345);
    assert(tracker.pending() && !tracker.active());
    assert(tracker.appliedAt() == 12345 && tracker.confirmation().angle == 45);
    assert(tracker.accept(b) == Decision::Busy);  // ACK sin enviar, no se pierde.
    assert(tracker.accept(a) == Decision::Duplicate);
    tracker.confirmationSent();
    assert(tracker.accept(a) == Decision::ReplayConfirmation);
    assert(tracker.pending() && !tracker.active());
    tracker.confirmationSent();
    assert(tracker.accept(b) == Decision::Start);
    tracker.cancelActive();
    assert(!tracker.pending() && !tracker.active());
    assert(tracker.accept(b) == Decision::Start);
    tracker.applied(0);  // uptime válido tras desbordamiento/reinicio del reloj.
    assert(tracker.pending() && tracker.appliedAt() == 0);
}

static void testEncoding() {
    char buffer[256];
    assert(encodeDistance(buffer, sizeof(buffer), 0, "sensor-01", 0) == 0);
    assert(encodeDistance(buffer, sizeof(buffer), std::numeric_limits<float>::infinity(), "sensor-01", 0) == 0);
    assert(encodeDistance(buffer, sizeof(buffer), 42, "sensor/bad", 0) == 0);
    assert(encodeDistance(buffer, 8, 42, "sensor-01", 0) == 0);
    assert(buffer[0] == '\0');
    const auto a = command(90, "cmd-1");
    assert(encodeState(buffer, sizeof(buffer), a, "actuator-01", 0, 100, 180) == 0);
}

static void decodeLines(int minimum, int maximum) {
    std::string line;
    while (std::getline(std::cin, line)) {
        std::vector<uint8_t> payload;
        for (size_t i = 0; i + 1 < line.size(); i += 2)
            payload.push_back(static_cast<uint8_t>(std::strtoul(line.substr(i, 2).c_str(), nullptr, 16)));
        CommandParser parser;
        ServoCommand result;
        if (parser.parse(payload.data(), payload.size(), minimum, maximum, result))
            std::cout << "OK\t" << result.angle << "\t" << result.command_id << '\n';
        else
            std::cout << "ERR\n";
    }
}

static void encodeExamples() {
    char output[256];
    for (float distance : {1e-20f, 42.5f, 400.0f}) {
        assert(encodeDistance(output, sizeof(output), distance, "sensor-01", UINT32_MAX) > 0);
        std::cout << output << '\n';
    }
    for (int angle : {0, 180}) {
        assert(encodeState(output, sizeof(output), command(angle, "cmd-fixture-1"),
                           "actuator-01", 12345, 0, 180) > 0);
        std::cout << output << '\n';
    }
}

int main(int argc, char** argv) {
    if (argc == 4 && std::strcmp(argv[1], "--decode") == 0) {
        decodeLines(std::atoi(argv[2]), std::atoi(argv[3]));
        return 0;
    }
    if (argc == 2 && std::strcmp(argv[1], "--encode") == 0) {
        encodeExamples();
        return 0;
    }
    testBackoff();
    testMotion();
    testCommandTracking();
    testEncoding();
    std::cout << "Backoff, rampa, duplicados, confirmacion pendiente y codificacion: OK.\n";
    return 0;
}
