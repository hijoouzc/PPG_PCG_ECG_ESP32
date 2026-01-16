idf_component_register(
    SRCS "sdcard.c"
    INCLUDE_DIRS "."
    REQUIRES
        fatfs
        sdmmc
        driver
        spi_flash
        freertos
        log
)
