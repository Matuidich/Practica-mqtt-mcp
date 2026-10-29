// Prueba el transporte real con APIs Wi-Fi/TCP/MQTT sustituidas, sin sockets.
#include "../../include/distributed/WifiMqttConnection.h"

int main() {
    iot_firmware::WifiMqttConnection network;
    assert(network.begin(project_config::MQTT_CLIENT_ID_ACTUATOR,
                         project_config::MQTT_TOPIC_LED_COMMAND));
    auto& io = connection_test::state();
    network.update();
    assert(io.wifi_starts == 1 && io.connects == 0);
    io.wifi = true;
    network.update();
    assert(network.connected() && io.connects == 1 && io.subscriptions == 1);
    assert(io.topic == project_config::MQTT_TOPIC_LED_COMMAND);
    assert(io.id == project_config::MQTT_CLIENT_ID_ACTUATOR);
    assert(network.publish(project_config::MQTT_TOPIC_LED_STATE, "{}", 2));
    io.mqtt = false;
    network.update();
    for (int time = 1; time < 1000; ++time) {
        led_test::state().now_ms = time;
        network.update();
    }
    assert(io.connects == 1);
    led_test::state().now_ms = 1000;
    io.subscribe_succeeds = false;
    network.update();
    assert(!network.connected() && io.subscriptions == 2 && io.connects == 2);
    led_test::state().now_ms = 2999;
    network.update();
    assert(io.connects == 2);
    led_test::state().now_ms = 3000;
    io.subscribe_succeeds = true;
    network.update();
    assert(network.connected() && io.connects == 3 && io.subscriptions == 3);
    io.wifi = false;
    network.update();
    assert(!network.connected());
    led_test::state().now_ms = 4000;
    network.update();
    assert(io.wifi_starts == 2);
    io.wifi = true;
    network.update();
    assert(network.connected() && io.subscriptions == 4);
    return 0;
}
