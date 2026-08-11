#include "car_lab_port.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char rx_line[256];
static uint16_t rx_pos = 0;

static int extract_key(const char *line, char *out, uint16_t n)
{
    const char *p = strstr(line, "\"key\":");
    if (!p) return 0;
    p = strchr(p, ':'); if (!p) return 0; p++;
    while (*p == ' ' || *p == '\"') p++;
    uint16_t i = 0;
    while (*p && *p != '\"' && *p != ',' && *p != '}' && i + 1 < n) out[i++] = *p++;
    out[i] = 0; return i > 0;
}

static int extract_value(const char *line, float *value)
{
    const char *p = strstr(line, "\"value\":");
    if (!p) return 0;
    p = strchr(p, ':'); if (!p) return 0;
    *value = (float)atof(p + 1); return 1;
}

static int extract_seq(const char *line, uint32_t *seq)
{
    const char *p = strstr(line, "\"seq\":");
    if (!p) return 0;
    p = strchr(p, ':'); if (!p) return 0;
    *seq = (uint32_t)strtoul(p + 1, NULL, 10);
    return 1;
}

static void send_ack(const char *key, float value, uint32_t seq, int has_seq, int ok, const char *error)
{
    char tx[192];
    int n;
    if (has_seq) {
        if (ok)
            n = snprintf(tx, sizeof(tx), "{\"type\":\"ACK\",\"key\":\"%s\",\"value\":%.6f,\"seq\":%lu,\"ok\":true}\n", key, value, (unsigned long)seq);
        else
            n = snprintf(tx, sizeof(tx), "{\"type\":\"ACK\",\"key\":\"%s\",\"seq\":%lu,\"ok\":false,\"error\":\"%s\"}\n", key, (unsigned long)seq, error ? error : "MCU rejected");
    } else {
        n = snprintf(tx, sizeof(tx), "{\"type\":\"ACK\",\"key\":\"%s\",\"value\":%.6f,\"ok\":%s}\n", key, value, ok ? "true" : "false");
    }
    if (n > 0 && n < (int)sizeof(tx))
        car_lab_uart_write((const uint8_t*)tx, (uint16_t)n);
}

static void handle_line(const char *line)
{
    char key[64]; float value = 0.0f; uint32_t seq = 0; int has_seq = extract_seq(line, &seq);
    if (!extract_key(line, key, sizeof(key))) return;

    if (strstr(line, "\"type\":\"SET\"")) {
        if (extract_value(line, &value)) {
            car_lab_set_parameter(key, value);
            send_ack(key, car_lab_get_parameter(key), seq, has_seq, 1, NULL);
        }
    } else if (strstr(line, "\"type\":\"GET\"")) {
        send_ack(key, car_lab_get_parameter(key), seq, has_seq, 1, NULL);
    } else if (strstr(line, "\"type\":\"CMD\"")) {
        if (!extract_value(line, &value)) return;
        if (strcmp(key, "emergency_stop") == 0) car_lab_emergency_stop();
        else if (strstr(key, "rpm_target")) car_lab_motor_set_rpm_target(key, value);
        else if (strstr(key, "motor")) car_lab_motor_set_percent(key, value);
        else car_lab_set_command_value(key, value);
        send_ack(key, value, seq, has_seq, 1, NULL);
    }
}

void car_lab_rx_byte(uint8_t byte)
{
    if (byte == '\r') return;
    if (byte == '\n') {
        rx_line[rx_pos] = 0;
        if (rx_pos) handle_line(rx_line);
        rx_pos = 0;
        return;
    }
    if ((uint16_t)(rx_pos + 1u) < (uint16_t)sizeof(rx_line)) rx_line[rx_pos++] = (char)byte;
    else rx_pos = 0;
}

void car_lab_send_telemetry(float target_rpm, float actual_rpm, float speed_error, float motor_pwm,
                            float speed, float target_yaw, float yaw, float yaw_error,
                            float target_yaw_rate, float gyro_z, float steering_output,
                            float battery, uint16_t battery_raw,
                            float left_current, float right_current,
                            float left_rpm, float right_rpm,
                            int32_t left_encoder, int32_t right_encoder)
{
    char tx[512];
    int n = snprintf(tx, sizeof(tx),
        "{\"type\":\"TEL\",\"data\":{"
        "\"target_rpm\":%.3f,\"actual_rpm\":%.3f,\"speed_error\":%.3f,\"motor_pwm\":%.3f,"
        "\"speed\":%.4f,\"target_yaw\":%.3f,\"yaw\":%.3f,\"yaw_error\":%.3f,"
        "\"target_yaw_rate\":%.3f,\"gyro_z\":%.3f,\"steering_output\":%.3f,"
        "\"battery\":%.3f,\"battery_raw\":%u,\"left_current\":%.3f,\"right_current\":%.3f,"
        "\"left_rpm\":%.3f,\"right_rpm\":%.3f,\"left_encoder\":%ld,\"right_encoder\":%ld}}\n",
        target_rpm, actual_rpm, speed_error, motor_pwm, speed, target_yaw, yaw, yaw_error,
        target_yaw_rate, gyro_z, steering_output, battery, (unsigned)battery_raw,
        left_current, right_current, left_rpm, right_rpm, (long)left_encoder, (long)right_encoder);
    if (n > 0 && n < (int)sizeof(tx)) car_lab_uart_write((const uint8_t*)tx, (uint16_t)n);
}


void car_lab_send_custom_loop(const char *target_key, float target,
                              const char *feedback_key, float feedback,
                              const char *error_key, float error,
                              const char *output_key, float output)
{
    char tx[320];
    int n = snprintf(tx, sizeof(tx),
        "{\"type\":\"TEL\",\"data\":{"
        "\"%s\":%.6f,\"%s\":%.6f,\"%s\":%.6f,\"%s\":%.6f}}\n",
        target_key, target, feedback_key, feedback, error_key, error, output_key, output);
    if (n > 0 && n < (int)sizeof(tx)) car_lab_uart_write((const uint8_t*)tx, (uint16_t)n);
}
