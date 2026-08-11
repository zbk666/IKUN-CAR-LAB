#include "car_lab_adc.h"

static uint16_t g_raw = 0;
static float g_filtered_v = 0.0f;
static uint8_t g_started = 0;

static float raw_to_battery(uint16_t raw)
{
    const float max_code = (float)((1u << CAR_LAB_ADC_BITS) - 1u);
    const float adc_v = ((float)raw / max_code) * CAR_LAB_ADC_VREF;
    const float divider = (CAR_LAB_BAT_R1 + CAR_LAB_BAT_R2) / CAR_LAB_BAT_R2;
    return (adc_v * divider) * CAR_LAB_BAT_GAIN + CAR_LAB_BAT_OFFSET;
}

void car_lab_power_init(void)
{
    g_raw = 0;
    g_filtered_v = 0.0f;
    g_started = 0;
}

void car_lab_power_update(void)
{
    const float alpha = 0.15f; /* simple low-pass filter */
    g_raw = car_lab_adc_read_battery_raw();
    float v = raw_to_battery(g_raw);
    if (!g_started) { g_filtered_v = v; g_started = 1; }
    else g_filtered_v += alpha * (v - g_filtered_v);
}

uint16_t car_lab_power_get_battery_raw(void) { return g_raw; }
float car_lab_power_get_battery_voltage(void) { return g_filtered_v; }
