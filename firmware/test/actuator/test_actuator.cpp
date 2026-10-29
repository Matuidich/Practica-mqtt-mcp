// Incluye la aplicación real; solo Arduino, Servo, configuración y transporte son dobles.
#include <cstdlib>
#include <iostream>

#include "../../history/servo/main.cpp"

using actuator_test::state;

static void advance(uint32_t duration_ms) {
    for (uint32_t elapsed = 0; elapsed < duration_ms; ++elapsed) {
        ++state().now_ms;
        application.update();
    }
}

static void deliver(std::string payload,
                    std::string topic = project_config::MQTT_TOPIC_SERVO_COMMAND) {
    application.onMessage(&topic[0], reinterpret_cast<uint8_t*>(&payload[0]), payload.size());
}

static void send(int angle, const char* id) {
    deliver("{\"angle\":" + std::to_string(angle) + ",\"command_id\":\"" + id + "\"}");
}

static void expectHolding(int angle) {
    const auto& io = state();
    assert(io.attached && io.angle == angle);
    assert(io.frequency_hz == 50 && io.minimum_us == 1000 && io.maximum_us == 2000);
    assert(io.pin == 25 && io.detach_calls == 0);
    // LOW solo al arrancar o en un fallo explícito, nunca al finalizar normalmente.
    assert(io.low_calls == io.pin_mode_calls);
}

static void expectApplied(int angle, const char* id, uint32_t applied_ms) {
    const auto& publication = state().publications.back();
    assert(publication.topic == project_config::MQTT_TOPIC_SERVO_STATE);
    assert(publication.pwm_active && publication.angle == angle);
    const std::string expected = "{\"angle\":" + std::to_string(angle) +
        ",\"command_id\":\"" + id + "\",\"device_id\":\"offline-actuator\",\"uptime_ms\":" +
        std::to_string(applied_ms) + ",\"status\":\"applied\"}";
    assert(publication.payload == expected);
    expectHolding(angle);
}

static void testStartup() {
    setup();
    advance(10000);
    assert(!state().attached && state().attach_calls == 0 && state().frequency_calls == 0);
    assert(state().low_calls == 1 && state().pin_mode_calls == 1);
    assert(state().writes.empty() && state().publications.empty());
}

static void testHoldAfterApplied() {
    setup();
    send(45, "hold-45");
    assert(state().writes.size() == 1 && state().angle == 90);
    for (int expected = 89; expected >= 45; --expected) {
        const auto count = state().writes.size();
        advance(24);
        assert(state().writes.size() == count);
        advance(1);
        assert(state().writes.size() == count + 1 && state().angle == expected);
    }
    assert(state().publications.empty());
    advance(499);
    assert(state().publications.empty());
    expectHolding(45);
    advance(1);
    assert(state().publications.size() == 1);
    expectApplied(45, "hold-45", 1625);
    const auto writes = state().writes.size();
    advance(10000);
    expectHolding(45);
    assert(state().writes.size() == writes && state().publications.size() == 1);
    assert(state().low_calls == 1);
}

static void testConsecutiveCommands() {
    setup();
    int previous = 90;
    size_t confirmations = 0;
    for (int target : {45, 90, 135, 135}) {
        const std::string id = "sequence-" + std::to_string(confirmations);
        const uint32_t duration = std::abs(target - previous) * 25 + 500;
        send(target, id.c_str());
        assert(state().attach_calls == 1 && state().frequency_calls == 1);
        advance(duration - 1);
        assert(state().publications.size() == confirmations);
        advance(1);
        ++confirmations;
        assert(state().publications.size() == confirmations);
        expectApplied(target, id.c_str(), state().now_ms);
        advance(3000);
        expectHolding(target);
        assert(state().attach_calls == 1 && state().frequency_calls == 1 && state().low_calls == 1);
        previous = target;
    }
}

static void testDuplicatesAndBusy() {
    setup();
    send(45, "original");
    send(45, "original");       // Duplicada activa.
    send(90, "original");       // Mismo ID con otro ángulo.
    send(135, "busy-other");    // ID distinto mientras está ocupado.
    assert(state().attach_calls == 1 && state().writes.size() == 1);
    advance(1625);
    assert(state().publications.size() == 1);
    expectApplied(45, "original", 1625);
    const auto writes = state().writes.size();
    send(45, "original");       // Reenvía confirmación sin mover o reconfigurar PWM.
    application.update();
    assert(state().publications.size() == 2 && state().writes.size() == writes);
    expectApplied(45, "original", 1625);
    send(135, "original");
    advance(3000);
    assert(state().publications.size() == 2 && state().writes.size() == writes);
    assert(state().attach_calls == 1 && state().frequency_calls == 1 && state().low_calls == 1);
}

static void rejectInvalidMessages() {
    for (const char* payload : {"{\"angle\":90}",
                               "{\"angle\":true,\"command_id\":\"bad\"}",
                               "{\"angle\":90,\"command_id\":\"bad\",\"other\":1}",
                               "{\"angle\":45,\"angle\":90,\"command_id\":\"bad\"}"})
        deliver(payload);
    send(-1, "too-low");
    send(181, "too-high");
    deliver("{\"angle\":45,\"command_id\":\"wrong-topic\"}", "other/commands/servo");
    advance(3000);
}

static void testValidation() {
    setup();
    rejectInvalidMessages();
    assert(state().attach_calls == 0 && state().writes.empty() && state().publications.empty());
    send(90, "valid");
    advance(500);
    expectApplied(90, "valid", state().now_ms);
    const auto writes = state().writes.size();
    rejectInvalidMessages();
    expectHolding(90);
    assert(state().publications.size() == 1 && state().writes.size() == writes);
    assert(state().attach_calls == 1 && state().frequency_calls == 1 && state().low_calls == 1);
}

static void testAttachFailure() {
    setup();
    state().attach_succeeds = false;
    send(45, "retry-after-failure");
    advance(3000);
    assert(!state().attached && state().writes.empty() && state().publications.empty());
    assert(state().low_calls == 2 && state().pin_mode_calls == 2);
    state().attach_succeeds = true;
    send(45, "retry-after-failure");
    advance(1625);
    assert(state().attach_calls == 2 && state().publications.size() == 1);
    expectApplied(45, "retry-after-failure", state().now_ms);
    assert(state().low_calls == 2);
}

static void testDisconnected() {
    setup();
    send(45, "offline");
    state().connected = false;
    advance(1625);
    expectHolding(45);
    assert(state().publications.empty());
    send(135, "blocked-by-pending");
    send(45, "offline");
    advance(5000);
    expectHolding(45);
    assert(state().publications.empty());
    state().connected = true;
    application.update();
    assert(state().publications.size() == 1);
    expectApplied(45, "offline", 1625);
    send(90, "after-reconnect");
    advance(1625);
    assert(state().publications.size() == 2);
    expectApplied(90, "after-reconnect", state().now_ms);
    assert(state().attach_calls == 1 && state().frequency_calls == 1 && state().low_calls == 1);
}

static void testPublishRetry() {
    setup();
    state().publish_succeeds = false;
    send(45, "pending");
    advance(1625);
    expectHolding(45);
    assert(state().publications.empty() && state().publish_attempts == 1);
    send(135, "blocked");
    advance(999);
    assert(state().publish_attempts == 1);
    advance(1);
    assert(state().publish_attempts == 2 && state().last_publish_attempt_ms == 2625);
    state().publish_succeeds = true;
    advance(1999);
    assert(state().publications.empty() && state().publish_attempts == 2);
    advance(1);
    assert(state().publications.size() == 1 && state().publish_attempts == 3);
    expectApplied(45, "pending", 1625);
    assert(state().attach_calls == 1 && state().frequency_calls == 1 && state().low_calls == 1);
}

static void testClockWrap() {
    setup();
    state().now_ms = UINT32_MAX - 100;
    send(135, "clock-wrap");
    advance(1624);
    assert(state().publications.empty());
    advance(1);
    assert(state().publications.size() == 1);
    expectApplied(135, "clock-wrap", 1524);
}

static void testWiringBlocked() {
    assert(!device_config::ACTUATOR_WIRING_CONFIRMED);
    setup();
    send(45, "not-authorized");
    advance(10000);
    assert(!state().attached && state().attach_calls == 0 && state().frequency_calls == 0);
    assert(state().pin_mode_calls == 0 && state().low_calls == 0);
    assert(state().writes.empty() && state().publications.empty());
}

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const std::string scenario = argv[1];
    if (scenario == "startup") testStartup();
    else if (scenario == "hold") testHoldAfterApplied();
    else if (scenario == "consecutive") testConsecutiveCommands();
    else if (scenario == "duplicates") testDuplicatesAndBusy();
    else if (scenario == "validation") testValidation();
    else if (scenario == "failure") testAttachFailure();
    else if (scenario == "disconnected") testDisconnected();
    else if (scenario == "publish-retry") testPublishRetry();
    else if (scenario == "clock-wrap") testClockWrap();
    else if (scenario == "wiring") testWiringBlocked();
    else return 2;
    std::cout << scenario << ": OK\n";
}
