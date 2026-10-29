#pragma once

#include "Arduino.h"
#include "distributed/Backoff.h"

namespace iot_firmware {
class WifiMqttConnection {
public:
    using Callback = void (*)(char*, uint8_t*, unsigned int);

    bool begin(const char*, const char*, Callback) { return true; }
    void update() {}
    bool connected() { return actuator_test::state().connected; }

    bool publish(const char* topic, const char* payload, size_t length) {
        auto& io = actuator_test::state();
        ++io.publish_attempts;
        io.last_publish_attempt_ms = io.now_ms;
        if (!io.connected || !io.publish_succeeds) return false;
        io.publications.push_back({topic, std::string(payload, length), io.attached, io.angle});
        return true;
    }
};
}  // namespace iot_firmware
