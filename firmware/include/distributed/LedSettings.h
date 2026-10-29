#pragma once

#include "distributed/DeviceSettings.h"

// Opciones nuevas: una copia Wi-Fi anterior sigue compilando y queda bloqueada.
// Para verificar/editar pines, definir estas macros en device_config.local.h.
#ifndef LED_WIRING_CONFIRMED
#define LED_WIRING_CONFIRMED false
#endif
#ifndef LED_RED_PIN
#define LED_RED_PIN 25
#endif
#ifndef LED_YELLOW_PIN
#define LED_YELLOW_PIN 26
#endif
#ifndef LED_GREEN_PIN
#define LED_GREEN_PIN 27
#endif

namespace led_config {
constexpr bool WIRING_CONFIRMED = LED_WIRING_CONFIRMED;
constexpr int RED_PIN = LED_RED_PIN;
constexpr int YELLOW_PIN = LED_YELLOW_PIN;
constexpr int GREEN_PIN = LED_GREEN_PIN;
constexpr bool outputPin(int pin) {
    return (pin >= 0 && pin <= 5) || (pin >= 12 && pin <= 19) ||
           (pin >= 21 && pin <= 23) || (pin >= 25 && pin <= 27) || pin == 32 || pin == 33;
}
static_assert(outputPin(RED_PIN) && outputPin(YELLOW_PIN) && outputPin(GREEN_PIN),
              "Los LED requieren GPIO de salida validos del ESP32.");
static_assert(RED_PIN != YELLOW_PIN && RED_PIN != GREEN_PIN && YELLOW_PIN != GREEN_PIN,
              "Cada LED necesita un GPIO diferente.");
}  // namespace led_config
