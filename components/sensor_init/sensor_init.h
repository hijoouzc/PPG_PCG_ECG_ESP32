/**
 * @file sensor_init.h 
 * @brief Cau hinh va dong bo cam bien PPG - PCG - ECG @ 1000Hz
 * @author Luong Huu Phuc (Modified)
 */

#ifndef SENSOR_INIT_H
#define SENSOR_INIT_H

#pragma once

#include <stdio.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/semphr.h>
#include "esp_log.h"
#include "esp_err.h"
#include "sensor_init.h"

/****Thu vien cho I2S****/
#include "driver/i2s_std.h"
#include "driver/i2c_master.h"
#include "driver/i2s_types.h"
#include "driver/i2s_common.h"
#include "driver/i2s_types_legacy.h"

/** Thu vien cho I2C */
#include <string.h>
#include <esp_timer.h>
#include "driver/i2c.h"
#include "driver/i2c_types.h"
#include "driver/gpio.h"
#include "max30102.h"

/** Thu vien cho ADC  */
#include "driver/adc.h"
#include "driver/ledc.h"

// --- CAU HINH HE THONG ---
#define SAMPLE_RATE_HZ      1000  // Muc tieu 1000Hz
#define PRINT_TASK_PRIORITY 5     // Uu tien cao nhat cho task in/xu ly

// --- I2S (PCG - INMP441) ---
#define I2S_PORT            I2S_NUM_0
#define DIN_PIN             33
#define BCLK_PIN            32
#define LRCL_PIN            25
#define I2S_SAMPLE_RATE     16000 
// Ty le downsample: 16000 / 1000 = 16. Nghia la cu 16 mau thi lay trung binh ra 1 mau
#define I2S_DOWNSAMPLE_RATIO 16 
#define DMA_DESC_NUM        6
#define DMA_FRAME_NUM       64    // Giam size de giam latency
// Buffer size cho Queue (chua duoc khoang 2 lan khung truyen de an toan)
#define I2S_QUEUE_LEN       256   

// --- I2C (PPG - MAX30102) ---
#define I2C_SDA_GPIO        21
#define I2C_SCL_GPIO        22
#define I2C_PORT            I2C_NUM_0
#define I2C_SPEED_HZ        400000 // Tang toc do I2C len 400kHz (Fast Mode) de kip doc trong 1ms
#define PPG_SAMPLE_RATE     1000

// --- ADC (ECG - AD8232) ---
// Luu y: ESP32 ADC1 Channel 6 la GPIO34
#define ADC_ECG_CHANNEL     ADC1_CHANNEL_6 
// Cap nhat DB_12 cho ESP-IDF v5.x
#define ADC_ATTEN_LEVEL     ADC_ATTEN_DB_12 

// --- GLOBAL HANDLES ---
extern QueueHandle_t i2s_data_queue; // Hang doi du lieu am thanh
extern SemaphoreHandle_t data_mutex; // Mutex bao ve bien toan cuc

// --- FUNCTION PROTOTYPES ---
// Ham khoi tao toan bo
void sensor_init_all(void);

// Cac Task Handle (Quan trong: Ten phai khop voi sensor_init.c)
void i2s_reader_task(void *pvParameter); 
void max30102_reader_task(void *pvParameter);
void processing_task(void *pvParameter);

#endif // SENSOR_INIT_H