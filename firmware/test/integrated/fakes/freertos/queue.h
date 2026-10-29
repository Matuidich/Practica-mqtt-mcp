#pragma once
#include <cstring>
#include "FreeRTOS.h"

struct FakeQueue {
    size_t item_size = 0;
    bool full = false;
    std::vector<uint8_t> data;
};
using QueueHandle_t = FakeQueue*;
inline QueueHandle_t xQueueCreate(unsigned int length, size_t item_size) {
    assert(length == 1);
    if (integrated_test::state().fail_queue) return nullptr;
    static FakeQueue queue;
    queue.item_size = item_size;
    queue.data.resize(item_size);
    queue.full = false;
    return &queue;
}
inline BaseType_t xQueueOverwrite(QueueHandle_t queue, const void* data) {
    assert(queue != nullptr);
    std::memcpy(queue->data.data(), data, queue->item_size);
    queue->full = true;
    ++integrated_test::state().overwrites;
    return pdPASS;
}
inline BaseType_t xQueueReceive(QueueHandle_t queue, void* data, TickType_t wait) {
    assert(queue != nullptr && wait == 0);
    if (!queue->full) return pdFALSE;
    std::memcpy(data, queue->data.data(), queue->item_size);
    queue->full = false;
    return pdTRUE;
}
inline BaseType_t xQueueReset(QueueHandle_t queue) {
    assert(queue != nullptr);
    queue->full = false;
    ++integrated_test::state().queue_resets;
    return pdPASS;
}
inline void vQueueDelete(QueueHandle_t queue) {
    assert(queue != nullptr);
    queue->full = false;
}
