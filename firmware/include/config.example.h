#pragma once

// Copiar a config.h al preparar el firmware. Ese archivo está ignorado por Git.
// La cabecera compartida se genera desde .env con python -m iot_shared sync.
// Esta plantilla no se incluye desde main.cpp y no configura ningún periférico.
#include "mqtt_config.local.h"

namespace project_config {
constexpr char WIFI_SSID[] = "";
constexpr char WIFI_PASSWORD[] = "";

// -1 significa pendiente de asignación; no es un pin utilizable.
constexpr int HC_SR04_TRIGGER_PIN = -1;
constexpr int HC_SR04_ECHO_PIN = -1;
constexpr int SERVO_PIN = -1;
}  // namespace project_config
