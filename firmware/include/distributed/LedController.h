#pragma once

#include "LedMessages.h"

namespace iot_firmware {
// Modelo puro: no GPIO, reloj, Wi-Fi o publicación. Una confirmación pendiente.
class LedController {
public:
    enum class Decision { Applied, Replay, Duplicate, Busy, ConflictingId, Invalid };

    Decision accept(const LedCommand& command, uint32_t now_ms) {
        if (!validLedCommand(command)) return Decision::Invalid;
        if (has_last_ && std::strcmp(last_.command_id, command.command_id) == 0) {
            if (last_.mask != command.mask || last_.values != command.values)
                return Decision::ConflictingId;
            if (pending_) return Decision::Duplicate;
            pending_ = true;
            return Decision::Replay;
        }
        if (pending_) return Decision::Busy;
        values_ = static_cast<uint8_t>((values_ & ~command.mask) | command.values);
        last_ = command;
        applied_ms_ = now_ms;
        has_last_ = pending_ = true;
        return Decision::Applied;
    }

    uint8_t values() const { return values_; }
    bool pending() const { return pending_; }
    const char* commandId() const { return last_.command_id; }
    uint32_t appliedAt() const { return applied_ms_; }
    void confirmationSent() { pending_ = false; }

private:
    LedCommand last_;
    uint8_t values_ = 0;
    uint32_t applied_ms_ = 0;
    bool has_last_ = false, pending_ = false;
};
}  // namespace iot_firmware
