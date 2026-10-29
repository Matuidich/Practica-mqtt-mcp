#pragma once
#include "FreeRTOS.h"

namespace integrated_test { struct TaskYield {}; }
inline BaseType_t xTaskCreatePinnedToCore(void (*task)(void*), const char*, uint32_t stack,
                                        void* context, unsigned int priority, void*, int core) {
    assert(stack == 8192 && priority == 1 && core == 0);
    auto& io = integrated_test::state();
    ++io.tasks;
    io.task_core = core;
    if (io.fail_task) return pdFALSE;
    io.task = task;
    io.task_context = context;
    return pdPASS;
}
inline void vTaskDelay(TickType_t ticks) {
    assert(ticks > 0);
    // Detiene únicamente la ejecución determinista de un ciclo de la tarea del PC.
    throw integrated_test::TaskYield{};
}
