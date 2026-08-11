# CAR LAB v1.3.1 - MCU → 上位机接入说明

## 一、最重要：MCU 到上位机到底发什么？

物理链路可以是 UART / USB串口 / 蓝牙串口 / BLE / TCP。
应用层统一使用：

**UTF-8 + JSON Lines**

也就是：

> 一行 = 一个 JSON 对象 + `\\n`

例如速度数据：

```json
{"type":"TEL","data":{"target_rpm":500.0,"actual_rpm":487.2,"speed_error":12.8,"motor_pwm":61.3}}
```

最后一定要发送换行：

```text
...61.3}}\n
```

## 二、TEL：实时遥测

### 速度环
```json
{"type":"TEL","data":{"target_rpm":500,"actual_rpm":487.2,"speed_error":12.8,"motor_pwm":61.3}}
```

### 航向环
```json
{"type":"TEL","data":{"target_yaw":30,"yaw":27.4,"yaw_error":2.6,"target_yaw_rate":36,"gyro_z":31.5,"steering_output":42,"speed":3.12}}
```

### 电源
```json
{"type":"TEL","data":{"battery":11.86,"battery_raw":3679,"left_current":1.24,"right_current":1.19}}
```

### 赛道
```json
{"type":"TEL","data":{"speed":3.12,"tracking_error":0.032,"gyro_z":18.5,"curvature":0.14,"lap_trigger":0}}
```

### 双电机
```json
{"type":"TEL","data":{"left_rpm":498.2,"right_rpm":501.4,"left_encoder":15324,"right_encoder":15392}}
```

字段名必须与车型 YAML 中的 `telemetry` / `*_key` 对应。

推荐遥测频率：50~200Hz。

## 三、SET：在线写参数

上位机发送：

```json
{"type":"SET","key":"speed_kp","value":1.25,"seq":42}
```

MCU 不要立即“口头答应”。正确流程：

1. 检查 key 是否存在
2. 检查 value 范围
3. 修改 RAM
4. 读取实际生效值
5. 回 ACK

成功：

```json
{"type":"ACK","key":"speed_kp","value":1.25,"seq":42,"ok":true}
```

失败：

```json
{"type":"ACK","key":"speed_kp","seq":42,"ok":false,"error":"out_of_range"}
```

## 四、GET：读取参数

```json
{"type":"GET","key":"speed_kp","seq":43}
```

返回：

```json
{"type":"ACK","key":"speed_kp","value":1.25,"seq":43,"ok":true}
```

## 五、CMD：目标/动作

目标速度：

```json
{"type":"CMD","key":"target_rpm","value":500}
```

左电机点动：

```json
{"type":"CMD","key":"left_motor","value":20}
```

急停：

```json
{"type":"CMD","key":"emergency_stop","value":true}
```

## 六、为什么上位机不是简单双向同步？

因为调参时用户可能快速连续修改：

```text
1.20 → 1.21 → 1.22 → 1.23 → 1.24
```

CAR LAB 现在做的是“可靠参数写入缓冲”：

```text
同一个 key：只保留最新值
不同 key：排队
一次只发送一个参数
等待 ACK
ACK 超时：自动重试
3次仍失败：不丢值，留在缓冲区
重新连接：继续发送
```

所以最终想要的 `1.24` 不会被前面的旧值堵住。

上位机还会校验：

```text
SET seq
==
ACK seq

并且：
ACK value ≈ SET value
```

确认后才显示：

```text
已确认 ✓
```

## 七、RAM / Flash

在线调参只改 RAM。

建议增加独立的“保存参数到 Flash”命令，不要每一次按 `+/-` 就写 Flash。

## 八、MSP 实现

UART RX 每收到 1 byte：

```c
car_lab_rx_byte(rx_byte);
```

周期发送：

```c
car_lab_send_telemetry(...);
```

参数修改在：

```c
car_lab_set_parameter(key, value);
```

实际回读：

```c
car_lab_get_parameter(key);
```

ACK 必须包含 seq。

## 九、安全

MCU 必须自己实现：
- PWM / RPM 限幅
- 参数上下限
- 通信超时停车
- 急停
- 电机故障保护

上位机不作为唯一安全层。
