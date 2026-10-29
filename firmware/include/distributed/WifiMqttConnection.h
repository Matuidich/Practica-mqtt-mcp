#pragma once

#include <Arduino.h>
#include <PubSubClient.h>
#include <WiFi.h>

#include "distributed/Backoff.h"
#include "distributed/DeviceSettings.h"

namespace iot_firmware {

class WifiMqttConnection {
public:
    using Callback = void (*)(char*, uint8_t*, unsigned int);

    WifiMqttConnection()
        : mqtt_(tcp_),
          wifi_retry_(project_config::MQTT_RECONNECT_MIN_DELAY_MS,
                      project_config::MQTT_RECONNECT_MAX_DELAY_MS),
          mqtt_retry_(project_config::MQTT_RECONNECT_MIN_DELAY_MS,
                      project_config::MQTT_RECONNECT_MAX_DELAY_MS) {}

    bool begin(const char* client_id, const char* subscription = nullptr,
               Callback callback = nullptr) {
        client_id_ = client_id;
        subscription_ = subscription;
        if (device_config::WIFI_SSID[0] == '\0') {
            Serial.println("Wi-Fi deshabilitado: configurar device_config.local.h.");
            return false;
        }
        // 1024 bytes de payload + tópico de hasta 219 bytes + cabecera MQTT.
        if (!mqtt_.setBufferSize(1536)) {
            Serial.println("Error: no hay memoria para el buffer MQTT.");
            return false;
        }
        tcp_.setConnectionTimeout(device_config::TCP_CONNECT_TIMEOUT_MS);
        mqtt_.setServer(project_config::MQTT_HOST, project_config::MQTT_PORT);
        mqtt_.setKeepAlive(project_config::MQTT_KEEPALIVE_S);
        mqtt_.setSocketTimeout(device_config::MQTT_SOCKET_TIMEOUT_S);
        if (callback != nullptr) mqtt_.setCallback(callback);
        WiFi.persistent(false);
        WiFi.mode(WIFI_STA);
        WiFi.setAutoReconnect(false);  // Una sola política de reintentos.
        enabled_ = true;
        return true;
    }

    void update() {
        if (!enabled_) return;
        const uint32_t now_ms = millis();
        if (WiFi.status() != WL_CONNECTED) {
            if (wifi_online_) {
                wifi_online_ = mqtt_online_ = false;
                tcp_.stop();
                wifi_retry_.failed(now_ms);
                Serial.println("Wi-Fi perdido; reintento con espera progresiva.");
            }
            if (wifi_connecting_ &&
                static_cast<uint32_t>(now_ms - wifi_started_ms_) >=
                    device_config::WIFI_CONNECT_TIMEOUT_MS) {
                WiFi.disconnect(false, false);
                wifi_connecting_ = false;
                wifi_retry_.failed(now_ms);
                Serial.println("Wi-Fi: intento agotado; se reintentara.");
            }
            if (!wifi_connecting_ && wifi_retry_.ready(now_ms)) {
                WiFi.begin(device_config::WIFI_SSID, device_config::WIFI_PASSWORD);
                wifi_started_ms_ = millis();
                wifi_connecting_ = true;
                Serial.println("Wi-Fi: iniciando intento de conexion.");
            }
            return;
        }
        if (!wifi_online_) {
            wifi_online_ = true;
            wifi_connecting_ = false;
            wifi_retry_.reset();
            mqtt_retry_.reset();
            Serial.println("Wi-Fi conectado; preparando MQTT.");
        }
        if (mqtt_.connected()) {
            if (!mqtt_.loop()) {
                mqtt_online_ = false;
                mqtt_retry_.failed(millis());
                Serial.println("MQTT: sesion perdida.");
            }
            return;
        }
        if (mqtt_online_) {
            mqtt_online_ = false;
            mqtt_retry_.failed(now_ms);
        }
        if (!mqtt_retry_.ready(now_ms)) return;

        // PubSubClient conecta de forma síncrona. Se limita TCP y espera CONNACK;
        // no hay while de reconexión. DNS depende de los límites de la pila Wi-Fi.
        bool connected = mqtt_.connect(client_id_);  // Sesión limpia MQTT 3.1.1.
        if (connected && subscription_ != nullptr) {
            connected = mqtt_.subscribe(subscription_, 0);  // En cada reconexión.
        }
        if (connected) {
            mqtt_online_ = true;
            mqtt_retry_.reset();
            Serial.println("MQTT conectado; suscripciones solicitadas.");
        } else {
            Serial.printf("MQTT: intento fallido, estado=%d.\n", mqtt_.state());
            mqtt_.disconnect();
            tcp_.stop();
            mqtt_retry_.failed(millis());
        }
    }

    bool connected() { return enabled_ && wifi_online_ && mqtt_.connected(); }

    bool publish(const char* topic, const char* payload, size_t length) {
        if (!connected()) return false;
        return mqtt_.publish(topic, reinterpret_cast<const uint8_t*>(payload),
                             static_cast<unsigned int>(length), false);
    }

private:
    WiFiClient tcp_;
    PubSubClient mqtt_;
    Backoff wifi_retry_, mqtt_retry_;
    const char* client_id_ = nullptr;
    const char* subscription_ = nullptr;
    uint32_t wifi_started_ms_ = 0;
    bool enabled_ = false, wifi_connecting_ = false;
    bool wifi_online_ = false, mqtt_online_ = false;
};
}  // namespace iot_firmware
