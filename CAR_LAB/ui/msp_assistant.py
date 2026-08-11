from PySide6.QtWidgets import QWidget,QVBoxLayout,QPlainTextEdit

TEXT='''CAR LAB v1.0 MSP 接入要点

1. UART/USB串口只是传输层，MCU 可以是 MSPM0、MSP430、STM32、ESP32 等。
2. 实时遥测建议 50~200Hz，上位机负责显示；PID 控制循环仍在 MCU 内部运行。
3. 速度环建议上传：target_rpm, actual_rpm, speed_error, motor_pwm。
4. 航向串级环建议上传：target_yaw, yaw, yaw_error, target_yaw_rate, gyro_z, steering_output, speed。
5. 电源监控建议上传：battery, battery_raw, left_current, right_current。
6. 在线调参通过 SET 修改 RAM 参数，MCU 返回 ACK；真正工程版建议另外实现 SAVE_FLASH 命令。
7. 角度误差必须做 ±180° 归一化，不能直接 target-actual。

examples/msp/ 中提供：
- car_lab_port.c/.h：JSON Lines 通信模板
- car_lab_adc.c/.h：ADC 电池采样、分压换算、校准与滤波模板

注意：ADC 引脚、DriverLib/SysConfig 初始化与具体芯片相关，因此模板故意不把某个 MSP 型号写死。
'''

class MspAssistant(QWidget):
    def __init__(self,config):
        super().__init__();root=QVBoxLayout(self);txt=QPlainTextEdit();txt.setReadOnly(True);txt.setPlainText(TEXT);root.addWidget(txt)
