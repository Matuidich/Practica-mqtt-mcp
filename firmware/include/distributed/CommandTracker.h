#pragma once

#include <cstring>

#include "WireMessages.h"

namespace iot_firmware {

// Una orden activa y una confirmación pendiente como máximo: no cola de movimientos.
class CommandTracker {
public:
    enum class Decision { Start, Duplicate, ReplayConfirmation, Busy, ConflictingId };

    Decision accept(const ServoCommand& command) {
        if (active_ || pending_) {
            const ServoCommand& current = active_ ? active_command_ : last_command_;
            if (std::strcmp(current.command_id, command.command_id) == 0)
                return current.angle == command.angle ? Decision::Duplicate : Decision::ConflictingId;
            return Decision::Busy;
        }
        if (has_last_ && std::strcmp(last_command_.command_id, command.command_id) == 0) {
            if (last_command_.angle != command.angle) return Decision::ConflictingId;
            pending_ = true;
            return Decision::ReplayConfirmation;
        }
        active_command_ = command;
        active_ = true;
        return Decision::Start;
    }

    void applied(uint32_t uptime_ms) {
        if (!active_) return;
        last_command_ = active_command_;
        applied_ms_ = uptime_ms;
        has_last_ = pending_ = true;
        active_ = false;
    }

    void cancelActive() { active_ = false; }
    void confirmationSent() { pending_ = false; }
    bool active() const { return active_; }
    bool pending() const { return pending_; }
    const ServoCommand& confirmation() const { return last_command_; }
    uint32_t appliedAt() const { return applied_ms_; }

private:
    ServoCommand active_command_, last_command_;
    uint32_t applied_ms_ = 0;
    bool active_ = false, pending_ = false, has_last_ = false;
};
}  // namespace iot_firmware
