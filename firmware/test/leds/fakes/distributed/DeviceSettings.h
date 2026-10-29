#pragma once
namespace project_config {
constexpr unsigned long MQTT_RECONNECT_MIN_DELAY_MS = 1000;
constexpr unsigned long MQTT_RECONNECT_MAX_DELAY_MS = 32000;
constexpr char MQTT_CLIENT_ID_ACTUATOR[] = "offline-actuator";
constexpr char MQTT_TOPIC_LED_COMMAND[] = "offline/commands/leds";
constexpr char MQTT_TOPIC_LED_STATE[] = "offline/state/leds";
constexpr char MQTT_HOST[] = "offline.invalid";
constexpr int MQTT_PORT = 1883, MQTT_KEEPALIVE_S = 60;
}
namespace device_config {
constexpr char ACTUATOR_DEVICE_ID[] = "offline-actuator";
constexpr char WIFI_SSID[] = "offline-test";
constexpr char WIFI_PASSWORD[] = "not-a-credential";
constexpr unsigned long TCP_CONNECT_TIMEOUT_MS = 1500, WIFI_CONNECT_TIMEOUT_MS = 10000;
constexpr unsigned int MQTT_SOCKET_TIMEOUT_S = 2;
}
