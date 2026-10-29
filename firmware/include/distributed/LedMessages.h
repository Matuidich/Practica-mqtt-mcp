#pragma once

#include "WireMessages.h"

namespace iot_firmware {
// Bits: 0 rojo, 1 amarillo, 2 verde. La máscara distingue omitir de apagar.
struct LedCommand {
    char command_id[MAX_IDENTIFIER_LENGTH + 1] = {};
    uint8_t mask = 0, values = 0;
};

inline bool validLedCommand(const LedCommand& command) {
    return validIdentifier(command.command_id) && command.mask > 0 && command.mask <= 7 &&
           (command.values & ~command.mask) == 0;
}

class LedCommandParser : private JsonReader {
public:
    bool parse(const uint8_t* payload, size_t length, LedCommand& output) {
        if (payload == nullptr || length == 0 || length > MAX_PAYLOAD_BYTES) return false;
        data_ = payload;
        length_ = length;
        position_ = 0;
        LedCommand candidate;
        bool id_seen = false, leds_seen = false;
        if (!take('{')) return false;
        for (int field = 0; field < 2; ++field) {
            char key[MAX_IDENTIFIER_LENGTH + 1] = {};
            if (!readIdentifier(key) || !take(':')) return false;
            if (std::strcmp(key, "command_id") == 0) {
                if (id_seen || !readIdentifier(candidate.command_id)) return false;
                id_seen = true;
            } else if (std::strcmp(key, "leds") == 0) {
                if (leds_seen || !readLeds(candidate)) return false;
                leds_seen = true;
            } else return false;
            if (take('}')) {
                whitespace();
                if (!id_seen || !leds_seen || position_ != length_ || !validLedCommand(candidate))
                    return false;
                output = candidate;
                return true;
            }
            if (!take(',')) return false;
        }
        return false;
    }

private:
    bool literal(const char* text) {
        whitespace();
        const size_t size = std::strlen(text);
        if (length_ - position_ < size || std::memcmp(data_ + position_, text, size) != 0)
            return false;
        position_ += size;
        return true;
    }

    bool readLeds(LedCommand& command) {
        if (!take('{')) return false;
        for (int field = 0; field < 3; ++field) {
            char color[MAX_IDENTIFIER_LENGTH + 1] = {};
            if (!readIdentifier(color) || !take(':')) return false;
            const uint8_t bit = std::strcmp(color, "red") == 0 ? 1 :
                (std::strcmp(color, "yellow") == 0 ? 2 : (std::strcmp(color, "green") == 0 ? 4 : 0));
            if (!bit || (command.mask & bit)) return false;
            bool on;
            if (literal("true")) on = true;
            else if (literal("false")) on = false;
            else return false;
            command.mask |= bit;
            if (on) command.values |= bit;
            if (take('}')) return true;
            if (!take(',')) return false;
        }
        return false;
    }
};

inline size_t encodeLedState(char* output, size_t capacity, uint8_t values,
                             const char* command_id, const char* device_id, uint32_t uptime_ms) {
    if (values > 7 || !validIdentifier(command_id) || !validIdentifier(device_id)) return 0;
    return encodedSize(std::snprintf(output, capacity,
        "{\"leds\":{\"red\":%s,\"yellow\":%s,\"green\":%s},\"command_id\":\"%s\","
        "\"device_id\":\"%s\",\"uptime_ms\":%lu,\"status\":\"applied\"}",
        values & 1 ? "true" : "false", values & 2 ? "true" : "false",
        values & 4 ? "true" : "false", command_id, device_id,
        static_cast<unsigned long>(uptime_ms)), output, capacity);
}
}  // namespace iot_firmware
