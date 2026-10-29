#include <cmath>
#include <iostream>
#include "../../src/integrated/main.cpp"

using integrated_test::state;

static void boot() {
    setup();
    assert(state().starts == 0);  // loop/setup no abren MQTT: solo la tarea de red.
    assert(state().tasks == 1 && state().task_core == 0 && state().task != nullptr);
    state().in_worker = true;
    try {
        state().task(state().task_context);
        assert(false && "La tarea debe ceder después de un ciclo.");
    } catch (const integrated_test::TaskYield&) {}
    state().in_worker = false;
    assert(state().starts == 1 && state().client_id == project_config::MQTT_CLIENT_ID);
    assert(state().subscription == project_config::MQTT_TOPIC_LED_COMMAND);
}

static void networkStep() {
    state().in_worker = true;
    application.updateNetwork();
    state().in_worker = false;
}

static void command(const char* id, const char* changes) {
    state().incoming.push_back({project_config::MQTT_TOPIC_LED_COMMAND,
        std::string("{\"command_id\":\"") + id + "\",\"leds\":" + changes + "}"});
    networkStep();
}

static void startAt(uint64_t milliseconds) {
    state().now_us = milliseconds * 1000;
    const int triggers = state().trigger_count;
    application.updateSensor();
    assert(state().trigger_count == triggers + 1);
    assert(state().now_us == milliseconds * 1000 + 12);
}

static void echo(uint32_t width_us) {
    state().now_us += 100;
    integrated_test::echoEdge(true);
    state().now_us += width_us;
    integrated_test::echoEdge(false);
    const uint64_t before = state().now_us;
    application.updateSensor();
    assert(state().now_us == before);  // poll no espera ni avanza el reloj.
}

static void measureAt(uint64_t milliseconds, uint32_t width_us) {
    startAt(milliseconds);
    echo(width_us);
}

static void expectAck(int values, const char* id, uint32_t applied_at) {
    char expected[320];
    assert(iot_firmware::encodeLedState(expected, sizeof(expected), values, id,
        device_config::ACTUATOR_DEVICE_ID, applied_at) > 0);
    assert(state().publications.back().topic == project_config::MQTT_TOPIC_LED_STATE);
    assert(state().publications.back().payload == expected);
    assert(state().publications.back().leds == values);
}

static void expectDistance(float centimeters) {
    const auto& publication = state().publications.back();
    assert(publication.topic == project_config::MQTT_TOPIC_DISTANCE);
    assert(publication.payload.find("\"distance_cm\":" + std::to_string(static_cast<int>(centimeters)))
        != std::string::npos);
    assert(publication.payload.find("\"device_id\":\"offline-sensor\"") != std::string::npos);
}

static void testBlocked() {
    assert(!led_config::WIRING_CONFIRMED);
    boot();
    assert(state().led_modes == 0 && state().led_writes == 0 && state().echo_modes == 1);
    command("blocked", "{\"red\":true,\"yellow\":true,\"green\":true}");
    assert(state().publications.empty());
    measureAt(1000, 5800);
    networkStep();
    expectDistance(100);
    assert(state().led_writes == 0 && state().ack_attempts == 0);
}

static void testCoexistence() {
    assert(led_config::WIRING_CONFIRMED);
    boot();
    assert(state().led_modes == 3 && state().led_writes == 3);
    assert(state().levels[25] == LOW && state().levels[26] == LOW && state().levels[27] == LOW);
    startAt(1000);
    const uint64_t before = state().now_us;
    command("coexist", "{\"red\":true,\"yellow\":false,\"green\":false}");
    assert(state().now_us == before);  // ECHO sigue pendiente, MQTT ya confirmó.
    expectAck(1, "coexist", 1000);
    echo(5800);
    networkStep();
    expectDistance(100);
    assert(state().levels[25] == HIGH && state().publications.size() == 2);
    command("yellow", "{\"yellow\":true}");
    expectAck(3, "yellow", millis());
    const int updates = state().updates;
    const uint64_t before_loop = state().now_us;
    loop();
    assert(state().updates == updates && state().now_us == before_loop + 1000);
}

static void testLatest() {
    boot();
    // La tarea de red deja de ejecutarse, simulando una conexión síncrona lenta.
    measureAt(1000, 5800);
    measureAt(2000, 2900);
    measureAt(3000, 1450);
    assert(state().publications.empty() && state().overwrites == 3);
    networkStep();
    expectDistance(25);
    assert(state().publications.size() == 1);
    networkStep();
    assert(state().publications.size() == 1);  // No reproduce la cola de lecturas antiguas.
    measureAt(4000, 580);
    state().now_us += project_config::DISTANCE_PUBLISH_INTERVAL_MS * 1000;
    networkStep();
    assert(state().publications.size() == 1);  // Muestra caducada, aunque siga conectado.
}

static void testReconnect() {
    boot();
    state().fail_ack = true;
    command("pending", "{\"green\":true}");
    state().connected = false;
    measureAt(1000, 5800);
    networkStep();
    measureAt(2000, 2900);
    networkStep();
    measureAt(3000, 1450);
    state().connected = true;
    state().fail_ack = false;
    networkStep();
    expectAck(4, "pending", 0);
    assert(state().distance_attempts == 0 && state().publications.size() == 1);
    measureAt(4000, 580);
    networkStep();
    expectDistance(10);
    assert(state().publications.size() == 2 && state().levels[27] == HIGH);
}

static void testRetry() {
    boot();
    state().fail_ack = true;
    command("retry", "{\"red\":true}");
    assert(state().ack_attempts == 1);
    measureAt(1000, 5800);
    networkStep();
    expectDistance(100);
    assert(state().ack_attempts == 2);
    measureAt(2000, 2900);
    networkStep();
    expectDistance(50);
    assert(state().ack_attempts == 2 && state().distance_attempts == 2);
    state().fail_ack = false;
    state().now_us = 3005000;
    networkStep();
    expectAck(1, "retry", 0);
    assert(state().ack_attempts == 3 && state().led_writes == 6);
}

static void testValidation() {
    boot();
    for (const char* payload : {"{}", "{\"command_id\":\"bad\",\"leds\":{\"red\":1}}",
         "{\"command_id\":\"bad\",\"leds\":{\"red\":true,\"red\":false}}",
         "{\"command_id\":\"bad\",\"leds\":{\"blue\":true}}"}) {
        state().incoming.push_back({project_config::MQTT_TOPIC_LED_COMMAND, payload});
        networkStep();
    }
    state().incoming.push_back({"offline/commands/servo", "{\"angle\":90,\"command_id\":\"old\"}"});
    networkStep();
    assert(state().publications.empty() && state().led_writes == 3);
    state().fail_ack = true;
    command("original", "{\"red\":true}");
    const int writes = state().led_writes;
    command("original", "{\"red\":true}");
    command("original", "{\"red\":false}");
    command("busy", "{\"yellow\":true}");
    assert(state().led_writes == writes && state().ack_attempts == 1);
    state().fail_ack = false;
    state().now_us = 1000000;
    networkStep();
    expectAck(1, "original", 0);
    command("original", "{\"red\":true}");
    expectAck(1, "original", 0);
    assert(state().led_writes == writes && state().publications.size() == 2);
}

static void testSonar() {
    iot_firmware::AsyncHcsr04 sonar(5, 18, 30000);
    sonar.begin();
    float centimeters = -1;
    assert(sonar.poll(centimeters) == iot_firmware::AsyncHcsr04::Result::Pending);
    for (uint32_t width : {58U, 116U, 5800U, 23200U, 23258U}) {
        assert(sonar.start() && !sonar.start());
        const uint64_t before = state().now_us;
        assert(sonar.poll(centimeters) == iot_firmware::AsyncHcsr04::Result::Pending);
        assert(state().now_us == before);
        state().now_us += 100;
        integrated_test::echoEdge(true);
        state().now_us += width;
        integrated_test::echoEdge(false);
        state().now_us += 40000;  // La ISR conserva un eco válido aun si poll llega tarde.
        const auto result = sonar.poll(centimeters);
        if (width >= 116 && width <= 23200) {
            assert(result == iot_firmware::AsyncHcsr04::Result::Valid);
            assert(std::fabs(centimeters - width / 58.0f) < 0.001f);
        } else assert(result == iot_firmware::AsyncHcsr04::Result::Invalid);
    }
    sonar.start();
    state().now_us += 30000;
    assert(sonar.poll(centimeters) == iot_firmware::AsyncHcsr04::Result::Invalid);
    sonar.start();
    state().now_us += 29000;
    integrated_test::echoEdge(true);
    state().now_us += 5800;
    integrated_test::echoEdge(false);
    assert(sonar.poll(centimeters) == iot_firmware::AsyncHcsr04::Result::Invalid);
    state().now_us = UINT32_MAX - 200ULL;
    sonar.start();
    state().now_us += 100;
    integrated_test::echoEdge(true);
    state().now_us += 5800;
    integrated_test::echoEdge(false);
    assert(sonar.poll(centimeters) == iot_firmware::AsyncHcsr04::Result::Valid);
    assert(std::fabs(centimeters - 100.0f) < 0.001f);
    sonar.end();
    assert(state().echo_isr == nullptr);
}

static void testNoEcho() {
    boot();
    startAt(1000);
    command("during-timeout", "{\"green\":true}");
    expectAck(4, "during-timeout", 1000);
    state().now_us += 30000;
    application.updateSensor();
    networkStep();
    assert(state().distance_attempts == 0);
    measureAt(2000, 5800);
    networkStep();
    expectDistance(100);
}

static void testWrap() {
    state().now_us = (UINT32_MAX - 500ULL) * 1000;
    const uint64_t started_ms = state().now_us / 1000;
    boot();
    measureAt(started_ms + 1000, 5800);
    networkStep();
    expectDistance(100);
    assert(state().trigger_count == 1 && millis() < 1000);
}

static void testAllocation(bool queue) {
    state().fail_queue = queue;
    state().fail_task = !queue;
    setup();
    state().now_us = 10000000;
    loop();
    assert(state().starts == 0 && state().task == nullptr && state().trigger_count == 0);
    assert(state().echo_isr == nullptr && state().levels[25] == LOW);
    assert(state().publications.empty());
}

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const std::string scenario = argv[1];
    if (scenario == "blocked") testBlocked();
    else if (scenario == "coexistence" || scenario == "contracts") testCoexistence();
    else if (scenario == "latest") testLatest();
    else if (scenario == "reconnect") testReconnect();
    else if (scenario == "retry") testRetry();
    else if (scenario == "validation") testValidation();
    else if (scenario == "sonar") testSonar();
    else if (scenario == "no-echo") testNoEcho();
    else if (scenario == "wrap") testWrap();
    else if (scenario == "fail-queue") testAllocation(true);
    else if (scenario == "fail-task") testAllocation(false);
    else return 2;
    if (scenario == "contracts")
        for (const auto& publication : state().publications)
            std::cout << publication.topic << '\t' << publication.payload << '\n';
    return 0;
}
