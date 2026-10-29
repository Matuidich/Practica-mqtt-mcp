#pragma once
#include "WiFi.h"
class PubSubClient {
public:
    explicit PubSubClient(WiFiClient&) {}
    bool setBufferSize(int) { return true; }
    void setServer(const char*, int) {}
    void setKeepAlive(int) {}
    void setSocketTimeout(int) {}
    void setCallback(void (*)(char*, uint8_t*, unsigned int)) {}
    bool connected() { return connection_test::state().mqtt; }
    bool loop() { return connected(); }
    bool connect(const char* id) {
        auto& io = connection_test::state();
        ++io.connects;
        io.id = id;
        io.mqtt = io.connect_succeeds;
        return io.mqtt;
    }
    bool subscribe(const char* topic, int qos) {
        assert(qos == 0);
        auto& io = connection_test::state();
        ++io.subscriptions;
        io.topic = topic;
        return io.subscribe_succeeds;
    }
    void disconnect() { connection_test::state().mqtt = false; }
    int state() { return -1; }
    bool publish(const char*, const uint8_t*, unsigned int, bool retained) {
        assert(!retained);
        return connected();
    }
};
