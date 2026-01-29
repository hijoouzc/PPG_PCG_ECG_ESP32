/**
 * @file sensor_init.h 
 * @brief Cau hinh va dong bo cam bien PPG - PCG - ECG @ 1000Hz (Optimized)
 */

#ifndef SENSOR_INIT_H
#define SENSOR_INIT_H

#pragma once

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "freertos/queue.h"
#include "esp_log.h"
#include "esp_err.h"
#include "esp_timer.h" // Thu vien thoi gian

/**** Driver Libraries ****/
#include "driver/i2s_std.h"
#include "driver/i2c_master.h" // Update for v5.x if needed, keeping legacy for compatibility
#include "driver/i2c.h"
#include "driver/gpio.h"
#include "driver/adc.h"
#include "max30102.h"

// --- CAU HINH HE THONG ---
#define SAMPLE_RATE_HZ      1000  
#define PRINT_TASK_PRIORITY 3     // Priority thap hon Processing Task
#define PROCESS_TASK_PRIORITY 5   // Priority cao nhat (Real-time)

// --- I2S (PCG - INMP441) ---
#define I2S_PORT            I2S_NUM_0
#define DIN_PIN             33
#define BCLK_PIN            32
#define LRCL_PIN            25
#define I2S_SAMPLE_RATE     16000 
#define I2S_DOWNSAMPLE_RATIO 16 
#define DMA_DESC_NUM        6
#define DMA_FRAME_NUM       64    
#define I2S_QUEUE_LEN       256   

// --- I2C (PPG - MAX30102) ---
#define I2C_SDA_GPIO        21
#define I2C_SCL_GPIO        22
#define I2C_PORT            I2C_NUM_0
#define I2C_SPEED_HZ        400000 
#define PPG_QUEUE_LEN       50    // Buffer cho PPG khi cam bien doc nhanh

// --- ADC (ECG - AD8232) ---
#define ADC_ECG_CHANNEL     ADC1_CHANNEL_6 // GPIO34
#define ADC_ATTEN_LEVEL     ADC_ATTEN_DB_12 

// --- DATA STRUCTURES ---
// 1. Struct chua mau PPG Red/IR
typedef struct {
    uint32_t red;
    uint32_t ir;
} ppg_sample_t;

// 2. Struct goi tin dong bo hoan chinh
typedef struct {
    int64_t timestamp; // Thoi gian he thong (us)
    int16_t pcg;
    uint32_t red;
    uint32_t ir;
    int ecg;
} sensor_packet_t;

// --- GLOBAL HANDLES ---
extern QueueHandle_t i2s_data_queue; // Queue PCG
extern QueueHandle_t ppg_data_queue; // Queue PPG (Moi)
extern QueueHandle_t logging_queue;  // Queue de in ra UART (Moi)

// --- FUNCTION PROTOTYPES ---
void sensor_init_all(void);

// Tasks
void i2s_reader_task(void *pvParameter); 
void max30102_reader_task(void *pvParameter);
void processing_task(void *pvParameter); // Sync 1000Hz
void logger_task(void *pvParameter);     // In du lieu

#endif // SENSOR_INIT_H