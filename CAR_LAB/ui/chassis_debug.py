from __future__ import annotations
import time
from collections import defaultdict
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QGroupBox,QLabel,QPushButton,QDoubleSpinBox,QPlainTextEdit


class ChassisDebugPage(QWidget):
    def __init__(self,bus,transport,config):
        super().__init__(); self.bus=bus; self.transport=transport; self.cfg=config.get("chassis_debug",{}); self.motors=self.cfg.get("motors",[]); self.last={}; self.test=None
        root=QVBoxLayout(self)
        imub=QGroupBox("IMU 零偏快速检查"); ig=QHBoxLayout(imub); self.imu=QLabel("gyro_z: --"); self.bias=QLabel("bias: --"); btn=QPushButton("采集 2 秒静止零偏"); btn.clicked.connect(self._start_imu); ig.addWidget(self.imu);ig.addWidget(self.bias);ig.addWidget(btn);root.addWidget(imub)
        mb=QGroupBox("多电机 RPM 一致性"); mg=QGridLayout(mb); self.pwm=QDoubleSpinBox();self.pwm.setRange(0,50);self.pwm.setValue(15);self.duration=QDoubleSpinBox();self.duration.setRange(.5,10);self.duration.setValue(2.0);run=QPushButton("开始一致性测试");run.clicked.connect(self._start_consistency);stop=QPushButton("全部停止");stop.clicked.connect(lambda:self.transport.command("emergency_stop",True));mg.addWidget(QLabel("PWM %"),0,0);mg.addWidget(self.pwm,0,1);mg.addWidget(QLabel("时间(s)"),0,2);mg.addWidget(self.duration,0,3);mg.addWidget(run,1,0,1,2);mg.addWidget(stop,1,2,1,2);root.addWidget(mb)
        self.out=QPlainTextEdit();self.out.setReadOnly(True);root.addWidget(self.out,1)
        bus.telemetry.connect(self._tel); self.timer=QTimer(self);self.timer.timeout.connect(self._tick);self.timer.start(50)
    def _tel(self,d):
        self.last.update(d); self.imu.setText(f"gyro_z: {float(d.get('gyro_z',0)):+.3f} °/s")
        if self.test:
            if self.test["kind"]=="imu": self.test["values"].append(float(d.get("gyro_z",0)))
            elif self.test["kind"]=="rpm":
                for m in self.motors:
                    k=m.get("rpm_key","")
                    if k in d:self.test["values"][m.get("label",m.get("key","motor"))].append(abs(float(d[k])))
    def _start_imu(self): self.test={"kind":"imu","end":time.monotonic()+2.0,"values":[]}; self.out.setPlainText("保持车辆完全静止，正在采集 gyro_z...")
    def _start_consistency(self):
        if not self.motors:return
        p=abs(self.pwm.value())
        for m in self.motors:self.transport.command(m.get("key","motor"),p)
        self.test={"kind":"rpm","end":time.monotonic()+self.duration.value(),"values":defaultdict(list)};self.out.setPlainText("正在以相同 PWM 采集多电机 RPM...")
    def _tick(self):
        if not self.test or time.monotonic()<self.test["end"]:return
        t=self.test;self.test=None
        if t["kind"]=="imu":
            vals=t["values"];bias=sum(vals)/len(vals) if vals else 0;self.bias.setText(f"bias: {bias:+.4f} °/s");self.out.setPlainText(f"IMU 静止采样完成\n平均 gyro_z = {bias:+.4f} °/s\n如偏置明显，应在 MCU 或参数中做零偏补偿。")
        else:
            self.transport.command("emergency_stop",True); means={k:(sum(v)/len(v) if v else 0) for k,v in t["values"].items()}; vals=[v for v in means.values() if v>0]
            diff=(max(vals)-min(vals))/max(sum(vals)/len(vals),1e-9)*100 if len(vals)>=2 else 0
            lines=["多电机一致性测试完成"]+[f"{k}: 平均 {v:.1f} RPM" for k,v in means.items()]+[f"最大相对差异约 {diff:.1f}%"]
            if diff>10:lines.append("差异较大：检查轮胎、机械阻力、电机/驱动器差异和编码器换算。")
            self.out.setPlainText("\n".join(lines))
