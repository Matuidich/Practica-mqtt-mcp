#pragma once

#include <cmath>
#include <cstdio>
#include <cstring>
#include <stddef.h>
#include <stdint.h>

namespace iot_firmware {

constexpr size_t MAX_PAYLOAD_BYTES = 1024;
constexpr size_t MAX_IDENTIFIER_LENGTH = 64;

struct ServoCommand {
    int angle = 0;
    char command_id[MAX_IDENTIFIER_LENGTH + 1] = {};
};

inline bool identifierCharacter(unsigned char value, bool first) {
    const bool alphanumeric = (value >= 'a' && value <= 'z') ||
                              (value >= 'A' && value <= 'Z') ||
                              (value >= '0' && value <= '9');
    return alphanumeric || (!first && (value == '.' || value == '_' || value == '-'));
}

inline bool validIdentifier(const char* value) {
    if (value == nullptr || value[0] == '\0') return false;
    for (size_t i = 0; i <= MAX_IDENTIFIER_LENGTH; ++i) {
        if (value[i] == '\0') return true;
        if (i == MAX_IDENTIFIER_LENGTH ||
            !identifierCharacter(static_cast<unsigned char>(value[i]), i == 0)) return false;
    }
    return false;
}

// Lector com?n de JSON estricto para contratos LED y servo hist?rico.
class JsonReader {
protected:
    void whitespace() {
        while (position_ < length_ &&
               (data_[position_] == ' ' || data_[position_] == '\t' ||
                data_[position_] == '\r' || data_[position_] == '\n')) ++position_;
    }

    bool take(char expected) {
        whitespace();
        if (position_ == length_ || data_[position_] != expected) return false;
        ++position_;
        return true;
    }

    static int hex(unsigned char value) {
        if (value >= '0' && value <= '9') return value - '0';
        if (value >= 'a' && value <= 'f') return value - 'a' + 10;
        if (value >= 'A' && value <= 'F') return value - 'A' + 10;
        return -1;
    }

    bool readIdentifier(char* output) {
        if (!take('"')) return false;
        size_t count = 0;
        while (position_ < length_) {
            unsigned int value = data_[position_++];
            if (value == '"') {
                output[count] = '\0';
                return count > 0;
            }
            if (value == '\\') {
                // Otros escapes JSON decodifican caracteres prohibidos en IDs.
                if (position_ == length_ || data_[position_++] != 'u' ||
                    length_ - position_ < 4) return false;
                value = 0;
                for (int digit = 0; digit < 4; ++digit) {
                    const int part = hex(data_[position_++]);
                    if (part < 0) return false;
                    value = value * 16 + static_cast<unsigned int>(part);
                }
            }
            if (value > 127 || count == MAX_IDENTIFIER_LENGTH ||
                !identifierCharacter(static_cast<unsigned char>(value), count == 0)) return false;
            output[count++] = static_cast<char>(value);
        }
        return false;
    }

    const uint8_t* data_ = nullptr;
    size_t length_ = 0, position_ = 0;
};

// Analizador del esquema ServoCommand, no de JSON arbitrario. Consume exactamente
// length bytes y admite orden de campos y escapes Unicode ASCII. No asigna heap.
// Detecta duplicados antes de poder perderlos en un mapa JSON y nunca convierte
// bool, texto, decimales o exponentes a enteros.
class CommandParser : private JsonReader {
public:
    bool parse(const uint8_t* payload, size_t length, int minimum, int maximum,
               ServoCommand& output) {
        if (payload == nullptr || length == 0 || length > MAX_PAYLOAD_BYTES ||
            minimum < 0 || minimum >= maximum || maximum > 180) return false;
        data_ = payload;
        length_ = length;
        position_ = 0;
        ServoCommand candidate;
        bool angle_seen = false, id_seen = false;
        if (!take('{')) return false;
        for (int field = 0; field < 2; ++field) {
            char key[MAX_IDENTIFIER_LENGTH + 1] = {};
            if (!readIdentifier(key) || !take(':')) return false;
            if (std::strcmp(key, "angle") == 0) {
                if (angle_seen || !readAngle(candidate.angle)) return false;
                angle_seen = true;
            } else if (std::strcmp(key, "command_id") == 0) {
                if (id_seen || !readIdentifier(candidate.command_id)) return false;
                id_seen = true;
            } else {
                return false;
            }
            if (take('}')) {
                whitespace();
                if (!angle_seen || !id_seen || position_ != length_ ||
                    candidate.angle < minimum || candidate.angle > maximum) return false;
                output = candidate;
                return true;
            }
            if (!take(',')) return false;
        }
        return false;
    }

private:
    bool readAngle(int& output) {
        whitespace();
        const bool negative = position_ < length_ && data_[position_] == '-';
        if (negative) ++position_;
        if (position_ == length_ || data_[position_] < '0' || data_[position_] > '9') return false;
        const bool leading_zero = data_[position_] == '0';
        int value = 0, digits = 0;
        while (position_ < length_ && data_[position_] >= '0' && data_[position_] <= '9') {
            if (leading_zero && digits > 0) return false;
            value = value * 10 + (data_[position_++] - '0');
            if (value > 180) return false;
            ++digits;
        }
        if (negative && value != 0) return false;
        output = value;  // JSON -0 es el entero 0, igual que en Python.
        return true;
    }

};

inline size_t encodedSize(int written, char* output, size_t capacity) {
    if (written <= 0 || static_cast<size_t>(written) >= capacity ||
        static_cast<size_t>(written) > MAX_PAYLOAD_BYTES) {
        if (capacity > 0) output[0] = '\0';
        return 0;
    }
    return static_cast<size_t>(written);
}

inline size_t encodeDistance(char* output, size_t capacity, float centimeters,
                             const char* device_id, uint32_t uptime_ms) {
    if (!std::isfinite(centimeters) || centimeters <= 0 || !validIdentifier(device_id)) return 0;
    return encodedSize(std::snprintf(output, capacity,
        "{\"distance_cm\":%.9g,\"device_id\":\"%s\",\"uptime_ms\":%lu}",
        static_cast<double>(centimeters), device_id, static_cast<unsigned long>(uptime_ms)),
        output, capacity);
}

inline size_t encodeState(char* output, size_t capacity, const ServoCommand& command,
                         const char* device_id, uint32_t uptime_ms, int minimum, int maximum) {
    if (command.angle < minimum || command.angle > maximum ||
        !validIdentifier(command.command_id) || !validIdentifier(device_id)) return 0;
    return encodedSize(std::snprintf(output, capacity,
        "{\"angle\":%d,\"command_id\":\"%s\",\"device_id\":\"%s\","
        "\"uptime_ms\":%lu,\"status\":\"applied\"}", command.angle, command.command_id,
        device_id, static_cast<unsigned long>(uptime_ms)), output, capacity);
}
}  // namespace iot_firmware
