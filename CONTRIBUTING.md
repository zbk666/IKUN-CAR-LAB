# 贡献指南 · Contributing

欢迎给 **IKUN · CAR LAB** 提 Issue 和 Pull Request！本项目最欢迎的两类贡献是：

1. **新增车型**（加一个 YAML 文件夹，无需写代码）——见下方[「贡献一个车型」](#贡献一个车型)。
2. 修 Bug / 优化功能 / 完善文档。

---

## 开发环境

- Python **3.10+**（开发用 3.12）
- 从源码运行：

```bash
cd CAR_LAB
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

启动后顶部「连接方式」选 **仿真** → **连接**，不接硬件即可跑通全部界面。改完代码建议先在仿真下自测一遍再提交。

## 项目结构速览

```
CAR_LAB/
├── main.py            程序入口
├── core/              数据总线 bus、协议 protocol、传输 transport(串口/BLE/TCP/仿真)、配置 config、分析
├── ui/                各功能页面（scope 示波器、speed_lab、heading_lab、chassis_motion 麦轮运动…）
└── vehicles/          车型（本指南重点）
```

- 上位机与 MCU 之间是**一行一条 JSON**（UTF-8，`\n` 分隔），四种类型：`TEL` 遥测 / `SET` 写参 / `GET` 读参 / `CMD` 指令 / `ACK` 确认。完整协议见 `CAR_LAB/docs/MCU_to_PC_通信协议与可靠参数同步开发手册_v1.3.1.md`。
- 各页面通过车型 YAML 里的 **key 映射**去 JSON 里取字段，所以**加车型 = 写一份字段映射**，不用改 Python。

---

## 贡献一个车型

车型系统是**插件化**的。两种布局都支持，推荐用目录式：

```
CAR_LAB/vehicles/
├── generic_diff_drive.yaml      # 旧：扁平文件（仍兼容）
└── my_new_car/                  # 新：一个文件夹一个车型（推荐）
    └── config.yaml
```

**加一个车型 = 加一个文件夹 + 一个 `config.yaml`**，重启软件后顶部「车型」下拉框自动出现，切换即重载字段映射。

### 最快的方式：复制现成的改

- 全向 / 多电机车 → 复制 `vehicles/mecanum/config.yaml`（含四轮 + Vx/Vy/Wz 解算层，字段最全）
- 两轮 / 差速 → 复制 `vehicles/generic_diff_drive.yaml`
- 想从零 → 复制 `vehicles/custom/config.yaml`（空白模板）

改里面的 `key` 让它们和你 MCU 实际发送/接收的 JSON 字段名对上即可。

### `config.yaml` 字段参考

> 原则：所有 `xxx_key` / `key` 都是**你的 MCU JSON 里的字段名**，软件按这些名字去取数/下发。用不到的块可以整段删掉。

```yaml
vehicle:                 # 【必填】车型身份
  id: my_new_car         #   唯一 id（也用作参数方案保存目录名）
  display_name: 我的车    #   下拉框显示名
  type: 四轮独立驱动       #   分类描述（随意）
  order: 30              #   排序，数字越小越靠前

transport:               # 连接默认值（软件里可改）
  type: serial           #   sim / serial / bluetooth_serial / ble / tcp
  port: COM3
  baudrate: 115200

speed_lab:               # 速度环页（把 key 对到你的字段）
  target_command_key: target_rpm   # 下发目标用的 CMD key
  target_key: target_rpm            # 遥测里“目标”字段
  actual_key: actual_rpm            # 遥测里“实际”字段
  error_key: speed_error
  output_key: motor_pwm
  params: {Kp: speed_kp, Ki: speed_ki, Kd: speed_kd}   # 三个 PID 参数 key

heading_lab:             # 航向页：外环航向角 + 内环角速度（可选）
  target_command_key: target_yaw
  yaw_key: yaw
  yaw_rate_key: gyro_z
  steering_key: steering_output
  outer_params: {Kp: heading_kp, Ki: heading_ki, Kd: heading_kd}
  inner_params: {Kp: yaw_rate_kp, Ki: yaw_rate_ki, Kd: yaw_rate_kd}

chassis_motion:          # 【麦轮/全向专属】底盘运动解算层，目标 vs 实际 Vx/Vy/Wz
  hint: 全向底盘：Vx 前后、Vy 横移、Wz 旋转
  axes:
  - {key: vx, label: 前后速度 Vx, unit: m/s, command_key: cmd_vx, target_key: target_vx, actual_key: vx, params: {Kp: vx_kp, Ki: vx_ki, Kd: vx_kd}}
  - {key: vy, label: 横移速度 Vy, unit: m/s, command_key: cmd_vy, target_key: target_vy, actual_key: vy, params: {Kp: vy_kp, Ki: vy_ki, Kd: vy_kd}}
  - {key: wz, label: 旋转速度 Wz, unit: "°/s", command_key: cmd_wz, target_key: target_wz, actual_key: wz, params: {Kp: wz_kp, Ki: wz_ki, Kd: wz_kd}}

pid_loops:               # 自定义环（可多个），配合“自定义环 + 专家模式”页
- key: my_loop
  name: 我的环
  target_command_key: custom_target
  target_key: custom_target
  feedback_key: custom_feedback
  error_key: custom_error
  output_key: custom_output
  params: {Kp: custom_kp, Ki: custom_ki, Kd: custom_kd}

power_monitor:           # 电源监控页（可选）
  battery_key: battery
  raw_key: battery_raw
  warning_voltage: 10.8
  critical_voltage: 10.2

parameters:              # 【重要】所有可读写参数的清单（“全部参数”页 + 参数方案都用它）
- {key: speed_kp, label: 速度环 Kp, default: 0.85}
- {key: speed_ki, label: 速度环 Ki, default: 0.10}
# … 上面各 params 里引用到的 key，都应在这里列出

chassis_debug:           # 电机层：单电机实验 / 多电机一致性 / 底盘调试页
  motors:
  - key: fl_motor        #   下发 PWM/RPM 用的命令 key
    label: 左前轮 FL
    rpm_key: fl_rpm      #   遥测里该轮转速字段
    encoder_key: fl_encoder
    current_key: fl_current
    pwm_key: fl_pwm
    rpm_command_key: fl_rpm_target
    pid_prefix: fl       #   在线 SET 时会发 fl_kp / fl_ki / fl_kd
    expected_encoder_sign: 1

scope_presets:           # 【可选】示波器专属工作组：一键选好一组通道
  我的工作组: [target_vx, vx, target_wz, wz, fl_rpm, fr_rpm, rl_rpm, rr_rpm]

channel_names:           # 【可选】给自定义字段起中文名（示波器/探针显示）
  vx: 实际 Vx
  target_vx: 目标 Vx
```

### 提交前自查

1. 软件能正常启动，下拉框能看到并切换到你的车型。
2. 顶部「参数检查」显示 **OK**（或只有 info 提示）——它会检查 key 冲突、`params` 引用的 key 是否在 `parameters` 里定义。
3. `parameters` 里列全了各 `params`/`inner_params`/`chassis_motion` 引用到的 key。
4. 有条件的话接真车或用仿真跑一下，确认字段能对上。

---

## 提交流程（Pull Request）

```bash
git checkout -b add-my-car        # 开一个分支
# 改动 / 加车型文件夹
git add -A
git commit -m "新增车型：我的车"
git push -u origin add-my-car
```

然后到 GitHub 仓库页点 **Compare & pull request**，说明你加了什么、在什么硬件/仿真上验证过。

## 代码风格

- 跟随现有文件的风格与命名；UI 用 PySide6，绘图用 pyqtgraph。
- 尽量只加不破坏现有车型和页面（本项目的一条铁律：**加功能不能让车型消失**）。
- 中文注释/文案没问题，本项目面向中文调车用户。

## 报告问题

到 [Issues](https://github.com/zbk666/IKUN-CAR-LAB/issues) 提，附上：软件版本（`VERSION.txt`）、复现步骤、`logs/` 里的日志、必要时贴车型 YAML。

感谢贡献 🚗💨
