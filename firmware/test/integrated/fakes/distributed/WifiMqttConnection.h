#pragma once
#include "Arduino.h"
#include "distributed/Backoff.h"
#include "distributed/DeviceSettings.h"

namespace iot_firmware {
class WifiMqttConnection {
public:
    using Callback = void (*)(char*, uint8_t*, unsigned int);
    bool begin(const char* client_id, const char* topic, Callback callback) {
        auto& io = integrated_test::state();
        assert(io.in_worker);
        ++io.starts;
        io.client_id = client_id;
        io.subscription = topic;
        io.callback = callback;
        return true;
    }
    void update() {
        auto& io = integrated_test::state();
        assert(io.in_worker);
        ++io.updates;
        if (!io.connected || io.incoming.empty()) return;
        auto message = io.incoming.front();
        io.incoming.erase(io.incoming.begin());
        io.callback(&message.first[0], reinterpret_cast<uint8_t*>(&message.second[0]),
                    message.second.size());
    }
    bool connected() {
        assert(integrated_test::state().in_worker);
        return integrated_test::state().connected;
    }
    bool publish(const char* topic, const char* payload, size_t length) {
        auto& io = integrated_test::state();
        assert(io.in_worker && io.connected);
        const bool ack = std::string(topic) == project_config::MQTT_TOPIC_LED_STATE;
        assert(ack || std::string(topic) == project_config::MQTT_TOPIC_DISTANCE);
        if (ack) ++io.ack_attempts;
        else ++io.distance_attempts;
        if (ack && io.fail_ack) return false;
        const int leds = io.levels[25] | (io.levels[26] << 1) | (io.levels[27] << 2);
        io.publications.push_back({topic, std::string(payload, length), leds});
        return true;
    }
};
}
