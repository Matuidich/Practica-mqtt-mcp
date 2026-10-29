#pragma once
#include "../../../leds/fakes/distributed/DeviceSettings.h"

namespace project_config {
constexpr char MQTT_CLIENT_ID[] = "offline-integrated";
constexpr char MQTT_TOPIC_DISTANCE[] = "offline/telemetry/distance";
constexpr unsigned long DISTANCE_PUBLISH_INTERVAL_MS = 1000;
}
namespace device_config {
constexpr int SENSOR_TRIGGER_PIN = 5, SENSOR_ECHO_PIN = 18;
constexpr unsigned long SENSOR_ECHO_TIMEOUT_US = 30000;
constexpr char SENSOR_DEVICE_ID[] = "offline-sensor";
}
