set(req sensor_init driver freertos esp_timer) #Yeu cau dung thu vien tu cac folder nay
idf_component_register(SRCS "PPG_PCG_ECG.c"
                      INCLUDE_DIRS "."
                      REQUIRES ${req})