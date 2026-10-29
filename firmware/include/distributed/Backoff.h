#pragma once

#include <stdint.h>

namespace iot_firmware {

// Política portable para ambos transportes; espera progresiva, sin delay().
class Backoff {
public:
    Backoff(uint32_t minimum_ms, uint32_t maximum_ms)
        : minimum_(minimum_ms), maximum_(maximum_ms), next_(minimum_ms) {}

    bool ready(uint32_t now_ms) const {
        return !waiting_ || static_cast<uint32_t>(now_ms - last_) >= delay_;
    }

    void failed(uint32_t now_ms) {
        last_ = now_ms;
        delay_ = next_;
        waiting_ = true;
        next_ = next_ > maximum_ / 2 ? maximum_ : next_ * 2;
    }

    void reset() {
        waiting_ = false;
        next_ = minimum_;
    }

    uint32_t delayMs() const { return delay_; }

private:
    uint32_t minimum_, maximum_, next_;
    uint32_t last_ = 0;
    uint32_t delay_ = 0;
    bool waiting_ = false;
};
}  // namespace iot_firmware
