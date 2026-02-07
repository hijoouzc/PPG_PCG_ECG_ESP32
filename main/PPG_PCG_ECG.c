#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_err.h"

#include "sensor_init.h" 

// --- TASK HANDLES ---
TaskHandle_t i2s_handle = NULL;
TaskHandle_t max30102_handle = NULL;
TaskHandle_t processing_handle = NULL;
TaskHandle_t logger_handle = NULL;

void app_main(void){
    ESP_ERROR_CHECK(i2cdev_init());
    sensor_init_all(); 

    // 2. Tao Task I2S (Producer 1)
    // Ghim vao CORE 0 de tach biet xu ly ngat DMA nang ne khoi Logic chinh
    xTaskCreatePinnedToCore(
        i2s_reader_task,     // Ham thuc thi
        "i2s_read",          // Ten task
        1024 * 6,            // Stack size (Tang len vi buffer I2S lon)
        NULL,                // Tham so
        5,                   // Priority (Trung binh)
        &i2s_handle,         // Handle
        0                    // CORE 0
    );

    // 3. Tao Task MAX30102 (Producer 2)
    // Chay o Core 1 cung voi Processing task
    xTaskCreatePinnedToCore(
        max30102_reader_task,
        "max_read",
        1024 * 4,
        NULL,
        4,                   // Priority (Thap hon I2S mot chut)
        &max30102_handle,
        1                    // CORE 1
    );

    // 4. Tao Task Xu ly Trung tam (Sync Hub)
    // Priority cao nhat (6) de dam bao chay dung 1ms/lan
    xTaskCreatePinnedToCore(
        processing_task,
        "proc_task",
        1024 * 6,
        NULL,
        6,                   // Priority CAO NHAT
        &processing_handle,
        1                    // CORE 1
    );

    // 5. Tao Task Ghi log/In an (Consumer)
    // Priority thap nhat (3) de chi chay khi CPU ranh
    xTaskCreatePinnedToCore(
        logger_task,
        "logger",
        1024 * 4,
        NULL,
        3,                   // Priority THAP NHAT
        &logger_handle,
        1                    // CORE 1
    );

    ESP_LOGI("MAIN", "System Started with Optimized Architecture 1000Hz");
}