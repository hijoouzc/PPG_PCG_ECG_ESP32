#include "sensor_init.h"


static const char *TAG = "SENSOR_FUSION";

// HANDLES
i2s_chan_handle_t rx_channel = NULL;
i2c_dev_t dev;
struct max30102_record record;

// QUEUES
QueueHandle_t i2s_data_queue = NULL;
QueueHandle_t ppg_data_queue = NULL;
QueueHandle_t logging_queue = NULL;  // Queue chuyen data sang task in

// CONFIG
void sensor_init_all(void){
    // 1. Config Queues
    i2s_data_queue = xQueueCreate(I2S_QUEUE_LEN, sizeof(int16_t));
    ppg_data_queue = xQueueCreate(PPG_QUEUE_LEN, sizeof(ppg_sample_t));
    logging_queue  = xQueueCreate(100, sizeof(sensor_packet_t)); // Buffer lon de tranh rot goi khi in cham

    if(i2s_data_queue == NULL || ppg_data_queue == NULL || logging_queue == NULL) {
        ESP_LOGE(TAG, "Failed to create Queues");
        return;
    }

    // 2. Config I2C (PPG - MAX30102)
    memset(&dev, 0, sizeof(i2c_dev_t));

    ESP_ERROR_CHECK(max30102_initDesc(&dev, I2C_PORT, I2C_SDA_GPIO, I2C_SCL_GPIO));
    if(max30102_readPartID(&dev) == ESP_OK) {
        ESP_LOGI("MAX30102", "Found MAX30102!");
    }
    else {
        ESP_LOGE("MAX30102", "Not found MAX30102");
    }
    max30102_clearFIFO(&dev); // Xoa du lieu rac trong FIFO
    
    // Sample Rate: 1000Hz, Pulse Width: 215us, ADC Range: 16384nA
    ESP_ERROR_CHECK(max30102_init(POWER_LED, SAMPLE_AVERAGE, LED_MODE, SAMPLE_RATE_HZ, PULSE_WIDTH, ADC_RANGE, &record, &dev));

    // 3. Config ADC (ECG - AD8232)
    adc1_config_width(ADC_WIDTH_BIT_12);
    adc1_config_channel_atten(ADC_CHANNEL, ADC_ATTEN_DB_12);

    // 4. Config I2S (PCG - INMP441)
    i2s_chan_config_t i2s_conf = I2S_CHANNEL_DEFAULT_CONFIG(I2S_PORT, I2S_ROLE_MASTER);
    i2s_conf.dma_desc_num = DMA_DESC_NUM;
    i2s_conf.dma_frame_num = DMA_FRAME_NUM;
    i2s_conf.auto_clear = true;
    ESP_ERROR_CHECK(i2s_new_channel(&i2s_conf, NULL, &rx_channel));

    i2s_std_config_t std_conf = {
        .clk_cfg = {
            .sample_rate_hz = I2S_SAMPLE_RATE,
            .clk_src = I2S_CLK_SRC_DEFAULT,
            .mclk_multiple = I2S_MCLK_MULTIPLE_1152, //Cang cao thi jitter(nhieu) cua BLCK va LRCL cang it 
        },
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

    ESP_LOGI(TAG, "All Sensors Initialized Successfully");
}

// TASK 1: read I2S 
void i2s_reader_task(void *pvParameter){
    int32_t raw_buffer[DMA_FRAME_NUM];
    size_t bytes_read = 0;
    int32_t sum_sample = 0;
    int sample_count = 0;
    int16_t final_sample = 0;

    while(1){
        if(i2s_channel_read(rx_channel, raw_buffer, sizeof(raw_buffer), &bytes_read, 1000 / portTICK_PERIOD_MS) == ESP_OK){
            int samples = bytes_read / sizeof(int32_t);
            for(int i=0; i<samples; i++){
                int16_t current_sample = (int16_t)(raw_buffer[i] >> 14);
                sum_sample += current_sample;
                sample_count++;

                if(sample_count >= I2S_DOWNSAMPLE_RATIO){
                    final_sample = (int16_t)(sum_sample / I2S_DOWNSAMPLE_RATIO);
                    // Timeout = 0 de tranh block neu processing task qua cham
                    xQueueSend(i2s_data_queue, &final_sample, 0); 
                    sum_sample = 0;
                    sample_count = 0;
                }
            }
        }
    }
}

// TASK 2: read MAX30102
// Su dung Queue thay vi Bien toan cuc de tranh mat mau
void max30102_reader_task(void *pvParameter){
    ppg_sample_t ppg_sample;
    
    while(1){
        // 1. Check data tren sensor
        max30102_check(&record, &dev);
        
        // 2. Doc het FIFO hien co
        while (max30102_available(&record)){
            ppg_sample.red = max30102_getFIFORed(&record);
            ppg_sample.ir = max30102_getFIFOIR(&record);
            max30102_nextSample(&record);

            // 3. Day vao Queue (Cho 10 ticks neu full)
            xQueueSend(ppg_data_queue, &ppg_sample, 10);
        }
        
        // Ngu 2ms de nhuong CPU, sensor co FIFO nen khong mat du lieu
        vTaskDelay(pdMS_TO_TICKS(2)); 
    }
}

// TASK 3: LOGGING 
// Chuyen viec in an sang task nay de khong lam cham task xu ly
void logger_task(void *pvParameter){
    sensor_packet_t data;
    char print_buf[64]; // Buffer chuoi in

    while(1){
        // Cho vo han den khi co du lieu trong Queue
        if(xQueueReceive(logging_queue, &data, portMAX_DELAY) == pdTRUE){
            // Format: Timestamp, PCG, Red, IR, ECG
            // Timestamp giup debug xem mau co deu 1ms khong
            // printf tu dong la blocking I/O, nhung o day no khong anh huong dong bo
            printf("%lld,%d,%lu,%lu,%d\n", data.timestamp, data.pcg, data.red, data.ir, data.ecg);
        }
    }
}

// TASK 4: SYNC HUB 1000Hz
void processing_task(void *pvParameter){
    TickType_t xLastWakeTime = xTaskGetTickCount();
    const TickType_t xFrequency = pdMS_TO_TICKS(1); // Chu ky 1ms
    
    sensor_packet_t packet;
    ppg_sample_t last_ppg = {0, 0}; // Luu gia tri cu de dien vao neu thieu
    ppg_sample_t new_ppg;
    
    while(1){
        // 1. Sync time (High Precision)
        packet.timestamp = esp_timer_get_time(); // Lay thoi gian he thong (us)

        // 2. PCG (Non-blocking)
        if(xQueueReceive(i2s_data_queue, &packet.pcg, 0) != pdTRUE){
            packet.pcg = 0; // Hoac giu gia tri cu
        }

        // 3. PPG (Non-blocking)
        // Vi MAX30102 co the cham hon hoac nhanh hon doi chut
        if(xQueueReceive(ppg_data_queue, &new_ppg, 0) == pdTRUE){
            last_ppg = new_ppg; // Cap nhat mau moi
        }
        // Luon su dung gia tri last_ppg (Zero-Order Hold)
        packet.red = last_ppg.red;
        packet.ir = last_ppg.ir;

        // 4. ECG (ADC Read)
        packet.ecg = adc1_get_raw(ADC_CHANNEL);

        // 5. Day goi tin sang Logger Task (Timeout = 0)
        // Neu Logger in qua cham va Queue day, goi tin nay se bi DROP de
        // bao ve tính thoi gian thuc cua he thong.
        xQueueSend(logging_queue, &packet, 0);

        // 6. Ngu chinh xac den next tick
        vTaskDelayUntil(&xLastWakeTime, xFrequency);
    }
}