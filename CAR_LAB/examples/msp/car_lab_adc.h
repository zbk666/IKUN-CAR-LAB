#ifndef CAR_LAB_ADC_H
#define CAR_LAB_ADC_H
#include <stdint.h>

/* Keep these values consistent with the vehicle YAML configuration. */
#ifndef CAR_LAB_ADC_BITS
#define CAR_LAB_ADC_BITS 12u
#endif
#ifndef CAR_LAB_ADC_VREF
#define CAR_LAB_ADC_VREF 3.300f
#endif
#ifndef CAR_LAB_BAT_R1
#define CAR_LAB_BAT_R1 30000.0f
#endif
#ifndef CAR_LAB_BAT_R2
#define CAR_LAB_BAT_R2 10000.0f
#endif
#ifndef CAR_LAB_BAT_GAIN
#define CAR_LAB_BAT_GAIN 1.000f
#endif
#ifndef CAR_LAB_BAT_OFFSET
#define CAR_LAB_BAT_OFFSET 0.000f
#endif

void car_lab_power_init(void);
void car_lab_power_update(void);
uint16_t car_lab_power_get_battery_raw(void);
float car_lab_power_get_battery_voltage(void);

/* Implement this one hook using the ADC peripheral of your exact MCU. */
uint16_t car_lab_adc_read_battery_raw(void);

#endif
