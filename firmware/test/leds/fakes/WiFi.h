#pragma once
#include "Arduino.h"
constexpr int WL_CONNECTED = 3, WIFI_STA = 1;
namespace connection_test {
struct State {
    bool wifi = false, mqtt = false, connect_succeeds = true, subscribe_succeeds = true;
    int wifi_starts = 0, connects = 0, subscriptions = 0;
    std::string topic, id;
};
inline State& state() { static State value; return value; }
}
class WiFiClient {
public:
    void setConnectionTimeout(unsigned long) {}
    void stop() { connection_test::state().mqtt = false; }
};
struct WiFiDouble {
    void persistent(bool) {}
    void mode(int) {}
    void setAutoReconnect(bool) {}
    int status() { return connection_test::state().wifi ? WL_CONNECTED : 0; }
    void begin(const char*, const char*) { ++connection_test::state().wifi_starts; }
    void disconnect(bool, bool) { connection_test::state().wifi = false; }
};
static WiFiDouble WiFi;
