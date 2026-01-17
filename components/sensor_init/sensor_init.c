#include "sensor_init.h"
#include "esp_log.h"
#include "driver/i2c.h"

// --- BIEN TOAN CUC ---
volatile uint32_t global_ppg_red = 0;
volatile uint32_t global_ppg_ir = 0;

// --- HANDLES ---
i2s_chan_handle_t rx_channel = NULL;
i2c_dev_t dev;
struct max30102_record record;
QueueHandle_t i2s_data_queue = NULL;
SemaphoreHandle_t data_mutex = NULL;

static const char *TAG = "SENSOR_FUSION";

// --- KHOI TAO ---
void sensor_init_all(void){
    // 1. Khoi tao Queue & Mutex
    i2s_data_queue = xQueueCreate(I2S_QUEUE_LEN, sizeof(int16_t));
    data_mutex = xSemaphoreCreateMutex();

    // 3. Khoi tao MAX30102
    memset(&dev, 0, sizeof(i2c_dev_t));
    dev.port = I2C_PORT; 
    
    // --- [QUAN TRONG] Lay dia chi tu file header max30102.h ---
    dev.addr = MAX30102_SENSOR_ADDR; 
    // ----------------------------------------------------------
    
    dev.cfg.sda_io_num = I2C_SDA_GPIO;
    dev.cfg.scl_io_num = I2C_SCL_GPIO;
    dev.cfg.master.clk_speed = I2C_SPEED_HZ;
    
    // Init config MAX30102
    ESP_ERROR_CHECK(i2c_dev_create_mutex(&dev));
    // Cac tham so (0x1F, 4, 2...) khop voi cac type (uint8_t, int) trong prototype ham init
    ESP_ERROR_CHECK(max30102_init(0x1F, 4, 2, 1000, 411, 16384, &record, &dev));

    // 4. Khoi tao ADC (Legacy)
    adc1_config_width(ADC_WIDTH_BIT_12);
    // Sua DB_11 thanh DB_12 cho ESP-IDF v5.x
    adc1_config_channel_atten(ADC_ECG_CHANNEL, ADC_ATTEN_DB_12);

    // 5. Khoi tao I2S STD
    i2s_chan_config_t i2s_conf = I2S_CHANNEL_DEFAULT_CONFIG(I2S_PORT, I2S_ROLE_MASTER);
    i2s_conf.dma_desc_num = DMA_DESC_NUM;
    i2s_conf.dma_frame_num = DMA_FRAME_NUM;
    i2s_conf.auto_clear = true;
    ESP_ERROR_CHECK(i2s_new_channel(&i2s_conf, NULL, &rx_channel));

    i2s_std_config_t std_conf = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(I2S_SAMPLE_RATE),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = BCLK_PIN,
            .ws = LRCL_PIN,
            .dout = I2S_GPIO_UNUSED,
            .din = DIN_PIN,
        },
    };
    std_conf.slot_cfg.slot_mask = I2S_STD_SLOT_LEFT;
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(rx_channel, &std_conf));
    ESP_ERROR_CHECK(i2s_channel_enable(rx_channel));

    ESP_LOGI(TAG, "All Sensors Initialized");
}

// --- TASK DOC I2S ---
void i2s_reader_task(void *pvParameter){
    int32_t raw_buffer[DMA_FRAME_NUM];
    size_t bytes_read = 0;
    
    // Bien dung de tinh trung binh
    int32_t sum_sample = 0;
    int sample_count = 0;
    int16_t final_sample = 0;

    while(1){
        // Doc khoi du lieu (Block cho den khi co data)
        if(i2s_channel_read(rx_channel, raw_buffer, sizeof(raw_buffer), &bytes_read, 1000 / portTICK_PERIOD_MS) == ESP_OK){
            int samples = bytes_read / sizeof(int32_t);
            
            for(int i=0; i<samples; i++){
                // 1. Lay gia tri 16-bit tu du lieu tho 32-bit
                int16_t current_sample = (int16_t)(raw_buffer[i] >> 14);
                
                // 2. Cong don
                sum_sample += current_sample;
                sample_count++;

                // 3. Khi du 16 mau (tuong duong 1ms troi qua o toc do 16kHz)
                if(sample_count >= I2S_DOWNSAMPLE_RATIO){
                    // Tinh trung binh
                    final_sample = (int16_t)(sum_sample / I2S_DOWNSAMPLE_RATIO);
                    
                    // Day vao Queue (Luc nay Queue nhan duoc dung 1000Hz)
                    xQueueSend(i2s_data_queue, &final_sample, 0);

                    // Reset bien dem
                    sum_sample = 0;
                    sample_count = 0;
                }
            }
        }
    }
}

// --- TASK DOC MAX30102 ---
void max30102_reader_task(void *pvParameter){
    while(1){
        // Check sensor data available
        max30102_check(&record, &dev);
        
        // Doc het FIFO
        if(xSemaphoreTake(data_mutex, 10) == pdTRUE){
            while (max30102_available(&record)){
                global_ppg_red = max30102_getFIFORed(&record);
                global_ppg_ir = max30102_getFIFOIR(&record);
                max30102_nextSample(&record);
            }
            xSemaphoreGive(data_mutex);
        }
        vTaskDelay(pdMS_TO_TICKS(5)); 
    }
}

// --- TASK TRUNG TAM (SYNC 1000Hz) ---
void processing_task(void *pvParameter){
    TickType_t xLastWakeTime;
    const TickType_t xFrequency = pdMS_TO_TICKS(1); // 1ms
    
    // Yeu cau: CONFIG_FREERTOS_HZ = 1000 trong menuconfig
    
    int16_t pcg_val = 0;
    int ecg_val = 0;
    uint32_t ppg_red_snap = 0, ppg_ir_snap = 0;

    xLastWakeTime = xTaskGetTickCount();

    while(1){
        // 1. PCG
        if(xQueueReceive(i2s_data_queue, &pcg_val, 0) != pdTRUE){
            // Queue empty handling if needed
        }

        // 2. ECG
        ecg_val = adc1_get_raw(ADC_ECG_CHANNEL);

        // 3. PPG Snapshot
        if(xSemaphoreTake(data_mutex, 0) == pdTRUE){
            ppg_red_snap = global_ppg_red;
            ppg_ir_snap = global_ppg_ir;
            xSemaphoreGive(data_mutex);
        }

        // 4. Print CSV: PCG, RED, IR, ECG
        printf("%d,%lu,%lu,%d\n", pcg_val, ppg_red_snap, ppg_ir_snap, ecg_val);

        // 5. Sync Delay
        vTaskDelayUntil(&xLastWakeTime, xFrequency);
    }
}
