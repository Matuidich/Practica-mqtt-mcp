#include <iostream>
#include <string>
#include "../../src/actuator/main.cpp"

using led_test::state;

static void deliver(std::string payload, std::string topic = project_config::MQTT_TOPIC_LED_COMMAND) {
    application.onMessage(&topic[0], reinterpret_cast<uint8_t*>(&payload[0]), payload.size());
}
static void send(const char* id, const char* changes) {
    deliver(std::string("{\"command_id\":\"") + id + "\",\"leds\":" + changes + "}");
}
static void advance(uint32_t duration) {
    for (uint32_t elapsed = 0; elapsed < duration; ++elapsed) {
        ++state().now_ms;
        application.update();
    }
}
static void expect(int values, const char* id, uint32_t applied_at) {
    assert(state().levels == values && !state().publications.empty());
    char expected[320];
    assert(iot_firmware::encodeLedState(expected, sizeof(expected), values, id,
                                     "offline-actuator", applied_at) > 0);
    assert(state().publications.back() == expected);
}
static void testStartup() {
    setup();
    advance(10000);
    assert(state().pin_modes == 3 && state().writes == 3 && state().levels == 0);
    assert(state().publications.empty());
    assert(state().subscription == project_config::MQTT_TOPIC_LED_COMMAND);
    assert(state().client_id == project_config::MQTT_CLIENT_ID_ACTUATOR);
}
static void testIndividual() {
    setup();
    const char* changes[] = {"{\"red\":true}", "{\"yellow\":true}", "{\"green\":true}",
                            "{\"red\":false}", "{\"yellow\":false}", "{\"green\":false}"};
    const int values[] = {1, 3, 7, 6, 4, 0};
    for (int index = 0; index < 6; ++index) {
        const std::string id = "individual-" + std::to_string(index);
        send(id.c_str(), changes[index]);
        assert(state().levels == values[index]);
        application.update();
        expect(values[index], id.c_str(), millis());
        assert(state().publications.size() == static_cast<size_t>(index + 1));
    }
}
static void testCombined() {
    setup();
    send("red-only", "{\"red\":true,\"yellow\":false,\"green\":false}");
    application.update();
    expect(1, "red-only", 0);
    send("yellow-only", "{\"green\":false,\"red\":false,\"yellow\":true}");
    application.update();
    expect(2, "yellow-only", 0);
    send("green-only", "{\"red\":false,\"yellow\":false,\"green\":true}");
    application.update();
    expect(4, "green-only", 0);
    send("all-off", "{\"red\":false,\"yellow\":false,\"green\":false}");
    application.update();
    expect(0, "all-off", 0);
    const int writes = state().writes;
    advance(10000);
    assert(state().levels == 0 && state().writes == writes);
}
static void testDuplicates() {
    setup();
    send("original", "{\"red\":true}");
    const int writes = state().writes;
    send("original", "{\"red\":true}");
    send("original", "{\"red\":false}");
    send("busy", "{\"green\":true}");
    assert(state().writes == writes && state().levels == 1);
    application.update();
    expect(1, "original", 0);
    advance(1000);
    send("original", "{\"red\":true}");
    application.update();
    expect(1, "original", 0);
    assert(state().publications.size() == 2 && state().writes == writes);
}
static void testValidation() {
    setup();
    for (const char* payload : {"{}", "[]", "{\"command_id\":\"x\",\"leds\":{}}",
         "{\"command_id\":\"x\",\"leds\":{\"red\":1}}",
         "{\"command_id\":\"x\",\"leds\":{\"blue\":true}}",
         "{\"command_id\":\"x\",\"leds\":{\"red\":true,\"red\":false}}"}) deliver(payload);
    deliver("{\"command_id\":\"x\",\"leds\":{\"red\":true}}", "offline/commands/servo");
    advance(100);
    assert(state().writes == 3 && state().publications.empty() && state().levels == 0);
}
static void testDisconnected() {
    setup();
    state().connected = false;
    send("offline", "{\"green\":true}");
    advance(5000);
    assert(state().levels == 4 && state().publications.empty() && state().attempts == 0);
    send("blocked", "{\"green\":false}");
    assert(state().levels == 4);
    state().connected = true;
    application.update();
    expect(4, "offline", 0);
    send("after-reconnect", "{\"red\":true}");
    application.update();
    expect(5, "after-reconnect", 5000);
}
static void testRetry() {
    setup();
    state().publish_succeeds = false;
    send("retry", "{\"yellow\":true}");
    application.update();
    assert(state().attempts == 1 && state().levels == 2);
    advance(999);
    assert(state().attempts == 1);
    advance(1);
    assert(state().attempts == 2);
    state().publish_succeeds = true;
    advance(1999);
    assert(state().attempts == 2);
    advance(1);
    assert(state().attempts == 3 && state().writes == 6);
    expect(2, "retry", 0);
}
static void testBlocked() {
    assert(!led_config::WIRING_CONFIRMED);
    setup();
    send("blocked", "{\"red\":true,\"yellow\":true,\"green\":true}");
    advance(10000);
    assert(state().pin_modes == 0 && state().writes == 0 && state().publications.empty());
}
static int decode() {
    std::string line;
    while (std::getline(std::cin, line)) {
        std::string payload;
        for (size_t index = 0; index + 1 < line.size(); index += 2)
            payload.push_back(static_cast<char>(std::stoi(line.substr(index, 2), nullptr, 16)));
        iot_firmware::LedCommand command;
        iot_firmware::LedCommandParser parser;
        if (parser.parse(reinterpret_cast<const uint8_t*>(payload.data()), payload.size(), command))
            std::cout << "OK\t" << command.command_id << '\t' << static_cast<int>(command.mask)
                      << '\t' << static_cast<int>(command.values) << '\n';
        else std::cout << "ERR\n";
    }
    return 0;
}
int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const std::string scenario = argv[1];
    if (scenario == "--decode") return decode();
    if (scenario == "--encode") {
        for (uint8_t values = 0; values < 8; ++values) {
            char payload[320];
            assert(iot_firmware::encodeLedState(payload, sizeof(payload), values,
                "fixture-1", "offline-actuator", UINT32_MAX) > 0);
            std::cout << payload << '\n';
        }
        return 0;
    }
    if (scenario == "startup") testStartup();
    else if (scenario == "individual") testIndividual();
    else if (scenario == "combined") testCombined();
    else if (scenario == "duplicates") testDuplicates();
    else if (scenario == "validation") testValidation();
    else if (scenario == "disconnected") testDisconnected();
    else if (scenario == "retry") testRetry();
    else if (scenario == "blocked") testBlocked();
    else return 2;
    return 0;
}
