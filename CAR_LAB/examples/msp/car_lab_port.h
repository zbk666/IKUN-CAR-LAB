#ifndef CAR_LAB_PORT_H
#define CAR_LAB_PORT_H
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

void car_lab_rx_byte(uint8_t byte);
void car_lab_send_telemetry(float target_rpm, float actual_rpm, float speed_error, float motor_pwm,
                            float speed, float target_yaw, float yaw, float yaw_error,
                            float target_yaw_rate, float gyro_z, float steering_output,
                            float battery, uint16_t battery_raw,
                            float left_current, float right_current,
                            float left_rpm, float right_rpm,
                            int32_t left_encoder, int32_t right_encoder);

/* Optional: send one user-defined PID loop without changing the main telemetry function. */
void car_lab_send_custom_loop(const char *target_key, float target,
                              const char *feedback_key, float feedback,
                              const char *error_key, float error,
                              const char *output_key, float output);

/* User must implement these hooks in the MCU project. */
void car_lab_uart_write(const uint8_t *data, uint16_t len);
void car_lab_motor_set_percent(const char *key, float percent);
void car_lab_motor_set_rpm_target(const char *key, float rpm);
void car_lab_set_parameter(const char *key, float value);
float car_lab_get_parameter(const char *key);
void car_lab_set_command_value(const char *key, float value);
void car_lab_emergency_stop(void);

#ifdef __cplusplus
}
#endif
#endif
