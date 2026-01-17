#include <stdio.h>
#include <string.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include "esp_log.h"
#include "esp_err.h"
#include "sensor_init.h"

/*** Task Handle Global Variables ***/
TaskHandle_t i2sReaderTask_handle = NULL;
TaskHandle_t maxReaderTask_handle = NULL;
TaskHandle_t processingTask_handle = NULL;

void app_main(void){
    // 1. Khoi tao thu vien I2C (Neu dung esp-idf-lib)
    // Neu trong sensor_init.c ban da tu goi i2c_driver_install thi co the can nhac bo dong nay 
    // hoac giu nguyen tuy vao cau truc thu vien max30102.h ban dang dung.
    ESP_ERROR_CHECK(i2cdev_init()); 

    // 2. Goi ham khoi tao toan bo cam bien & Queue/Mutex tu sensor_init.c
    sensor_init_all(); 

    // 3. Tao Task
    
    // --- Task 1: I2S Reader (INMP441) ---
    // Core 0: Thuong dung cho tac vu nen/he thong. I2S dung DMA nen khong ton CPU, 
    // nhung viec copy vao Queue nen de o Core rieng de tranh anh huong Logic chinh.
    // Priority: 6 (Rat cao) -> De khong bi tran buffer DMA
    xTaskCreatePinnedToCore(i2s_reader_task, "I2S_Read", 8192, NULL, 6, &i2sReaderTask_handle, 0);

    // --- Task 2: MAX30102 Reader (PPG) ---
    // Core 1: Chay cung core voi ung dung chinh
    // Priority: 4 (Trung binh) -> I2C toc do thap hon, co the cho doi duoc
    xTaskCreatePinnedToCore(max30102_reader_task, "PPG_Read", 4096, NULL, 4, &maxReaderTask_handle, 1);

    // --- Task 3: Processing & Print (ECG + Sync) ---
    // Day la task quan trong nhat ("Heartbeat" 1000Hz)
    // No se doc ECG truc tiep va lay du lieu tu 2 task kia de in ra.
    // Priority: 5 (Cao) -> Dam bao chay dung 1ms/lan
    xTaskCreatePinnedToCore(processing_task, "Process_Sync", 4096, NULL, 5, &processingTask_handle, 1);
    
    ESP_LOGI("MAIN", "System Started with 1000Hz Sampling Rate...");
}