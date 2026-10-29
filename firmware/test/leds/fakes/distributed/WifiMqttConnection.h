#pragma once
#include "Arduino.h"
#include "distributed/Backoff.h"
#include "distributed/DeviceSettings.h"
namespace iot_firmware {
class WifiMqttConnection {
public:
    using Callback = void (*)(char*, uint8_t*, unsigned int);
    bool begin(const char* id, const char* topic, Callback) {
        led_test::state().client_id = id;
        led_test::state().subscription = topic;
        return true;
    }
    void update() {}
    bool connected() { return led_test::state().connected; }
    bool publish(const char* topic, const char* payload, size_t length) {
        assert(std::string(topic) == project_config::MQTT_TOPIC_LED_STATE);
        auto& io = led_test::state();
        ++io.attempts;
        if (!io.connected || !io.publish_succeeds) return false;
        io.publications.push_back(std::string(payload, length));
        return true;
    }
};
}
