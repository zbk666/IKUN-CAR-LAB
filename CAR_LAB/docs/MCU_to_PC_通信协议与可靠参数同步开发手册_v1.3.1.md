# CAR LAB v1.3.1 MCU ↔ PC 开发手册

## 目标

新开发者只看这一份就能完成 MCU 接入。

## 1. 应用层格式

所有链路统一：

```text
UTF-8 JSON Lines
一帧 = 一个 JSON 对象 + `\\n`
```

## 2. 三种消息类型

### TEL
MCU → PC，周期上传实时状态。

```json
{"type":"TEL","data":{"speed":1.52,"actual_rpm":487.2,"battery":11.86}}
```

### SET
PC → MCU，修改参数。

```json
{"type":"SET","key":"speed_kp","value":1.25,"seq":42}
```

### GET
PC → MCU，读取参数。

```json
{"type":"GET","key":"speed_kp","seq":43}
```

### ACK
MCU → PC，对 SET / GET 做可靠确认。

```json
{"type":"ACK","key":"speed_kp","value":1.25,"seq":42,"ok":true}
```

失败：

```json
{"type":"ACK","key":"speed_kp","seq":42,"ok":false,"error":"out_of_range"}
```

### CMD
PC → MCU，发送目标或动作。

```json
{"type":"CMD","key":"target_rpm","value":500}
```

## 3. 字段规则

### 参数 key

它代表“可被上位机写入的变量”。

```text
speed_kp
speed_ki
heading_kp
yaw_rate_kp
left_motor_kp
```

要求：
- 唯一
- ASCII snake_case
- 不含空格
- 不与 telemetry key 重名
- 不与 control key 重名

### 遥测 key

它代表“MCU 报给上位机的状态”。

```text
actual_rpm
gyro_z
battery
tracking_error
```

## 4. 推荐实时字段

### Speed Lab

```text
target_rpm
actual_rpm
speed_error
motor_pwm
```

### Heading Lab

```text
target_yaw
yaw
yaw_error
target_yaw_rate
gyro_z
steering_output
speed
```

### Motor Lab

```text
left_rpm
left_encoder
left_current
left_pwm
right_rpm
right_encoder
right_current
right_pwm
```

四电机继续使用：

```text
front_left_*
rear_left_*
front_right_*
rear_right_*
```

### Power Monitor

```text
battery
battery_raw
left_current
right_current
```

### Track / Corner Analyzer

```text
speed
tracking_error
gyro_z
curvature
track_progress
lap_trigger
```

`lap_trigger` 采用 `0 -> 1` 脉冲。

## 5. 参数同步机制

CAR LAB 不是“发出去就算成功”。

写参数流程：

```text
用户改变 Kp
↓
进入缓冲区
↓
检查 key
↓
同 key 合并旧值
↓
等待前一个操作完成
↓
发送 SET(seq)
↓
等待 ACK
↓
检查 seq
↓
检查实际回读值
↓
显示“已确认”
```

### 快速连续调参

输入：

```text
1.20
1.21
1.22
1.23
1.24
```

内部不会产生 5 个必须全部发送的旧任务，而是最终发送：

```text
1.24
```

### 多参数

例如：

```text
speed_kp
speed_ki
speed_kd
```

严格串行：

```text
SET Kp → ACK
SET Ki → ACK
SET Kd → ACK
```

避免多个 SET 同时飞出去造成竞态。

### 超时与重试

当前默认：

```text
ACK timeout = 600ms
retry = 3
defer = 1s
```

3 次仍无 ACK：

```text
不删除目标值
→ 放回缓冲区
→ 稍后重试
→ 断线后重连继续
```

### ACK 值检查

例如：

```text
SET 1.250
ACK 1.250
```

才算正常。

若：

```text
SET 1.250
ACK 0.800
```

状态：

```text
回读不一致
```

继续重试，而不是假装成功。

## 6. 参数冲突检查

软件会检查：

```text
parameters[] 重复 key
PID 映射引用不存在的 key
parameter 与 telemetry 重名
parameter 与 control 重名
parameter 与目标 CMD 重名
```

严重冲突会在顶部显示。

## 7. MCU 推荐实现

伪代码：

```c
on_set(key, value, seq)
{
    if (!parameter_exists(key)) {
        ack_fail(key, seq, "unknown_key");
        return;
    }

    if (!parameter_in_range(key, value)) {
        ack_fail(key, seq, "out_of_range");
        return;
    }

    set_parameter_to_ram(key, value);

    float actual = get_parameter(key);

    ack_ok(key, actual, seq);
}
```

## 8. Flash

不要每次在线调参都写 Flash。

建议：

```text
SET
→ RAM

SAVE
→ Flash
```

## 9. 测试顺序

1. 用仿真连接
2. 发送 GET
3. 确认 ACK
4. 发送 SET
5. 确认 ACK seq
6. 连续快速修改同一 Kp
7. 检查最后值是否正确
8. 断开连接
9. 修改参数
10. 重新连接
11. 确认缓冲区最终继续发送

## 10. 安全

MCU 必须自己处理：
- 参数限幅
- PWM 限幅
- RPM 限幅
- 通信超时
- 急停
- 故障保护

PC 软件不应该成为唯一安全层。
