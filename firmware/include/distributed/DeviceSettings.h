#pragma once

// El archivo generado mantiene el mismo UUID, tópicos y límites de iot_shared.
#include "mqtt_config.local.h"

#if __has_include("device_config.local.h")
#include "device_config.local.h"
#else
#include "device_config.example.h"
#endif

static_assert(project_config::SERVO_MIN_ANGLE >= 0 &&
                  project_config::SERVO_MIN_ANGLE < project_config::SERVO_MAX_ANGLE &&
                  project_config::SERVO_MAX_ANGLE <= 180,
              "Limites de servo invalidos; revisar .env y ejecutar iot_shared sync.");
static_assert(device_config::SERVO_STEP_INTERVAL_MS > 0 &&
                  device_config::SERVO_SETTLE_MS > 0,
              "La temporizacion del servo debe ser positiva.");
static_assert(project_config::DISTANCE_PUBLISH_INTERVAL_MS >= 60,
              "El HC-SR04 necesita al menos 60 ms entre disparos.");
