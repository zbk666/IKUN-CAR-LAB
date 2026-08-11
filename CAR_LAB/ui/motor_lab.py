from __future__ import annotations
import time
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QGroupBox,QLabel,QPushButton,QComboBox,QDoubleSpinBox,QTableWidget,QTableWidgetItem,QCheckBox,QMessageBox,QPlainTextEdit


class MotorLab(QWidget):
    def __init__(self,bus,transport,config):
        super().__init__();self.bus=bus;self.transport=transport;self.cfg=config.get("chassis_debug",{});self.motors=self.cfg.get("motors",[]);self.last={};self.encoder_test=None
        root=QVBoxLayout(self);ctrl=QGroupBox("单电机安全实验");g=QGridLayout(ctrl)
        self.unlock=QCheckBox("解锁电机实验（实车先架空）");self.motor=QComboBox();[self.motor.addItem(m.get("label",m.get("key","motor"))) for m in self.motors];self.mode=QComboBox();self.mode.addItems(["PWM %","目标 RPM"]);self.value=QDoubleSpinBox();self.value.setRange(-10000,10000);self.value.setValue(15)
        f=QPushButton("正向运行");r=QPushButton("反向运行");s=QPushButton("停止当前");allstop=QPushButton("全部急停");enc=QPushButton("编码器方向检查")
        f.clicked.connect(lambda:self._run(abs(self.value.value())));r.clicked.connect(lambda:self._run(-abs(self.value.value())));s.clicked.connect(lambda:self._run(0,force=True));allstop.clicked.connect(lambda:self.transport.command("emergency_stop",True));enc.clicked.connect(self._encoder_check)
        g.addWidget(self.unlock,0,0,1,4);g.addWidget(QLabel("电机"),1,0);g.addWidget(self.motor,1,1);g.addWidget(QLabel("模式"),1,2);g.addWidget(self.mode,1,3);g.addWidget(QLabel("值"),2,0);g.addWidget(self.value,2,1);g.addWidget(f,3,0);g.addWidget(r,3,1);g.addWidget(s,3,2);g.addWidget(allstop,3,3);g.addWidget(enc,4,0,1,4);root.addWidget(ctrl)
        pb=QGroupBox("当前电机 PID（在线 SET）");pg=QGridLayout(pb);self.pid={}
        for c,k in enumerate(("kp","ki","kd")):
            sp=QDoubleSpinBox();sp.setDecimals(5);sp.setRange(-9999,9999);sp.setSingleStep(.01);self.pid[k]=sp;pg.addWidget(QLabel(k.upper()),0,c);pg.addWidget(sp,1,c)
        send=QPushButton("下发当前电机 PID");send.clicked.connect(self._send_pid);pg.addWidget(send,2,0,1,3);root.addWidget(pb)
        self.table=QTableWidget(0,7);self.table.setHorizontalHeaderLabels(["电机","RPM","Encoder","Current","PWM","方向期望","key"]);root.addWidget(self.table,1);self.result=QPlainTextEdit();self.result.setReadOnly(True);self.result.setMaximumHeight(120);root.addWidget(self.result)
        bus.telemetry.connect(self._tel);self.timer=QTimer(self);self.timer.timeout.connect(self._tick);self.timer.start(50);self._refresh()
    def _selected(self):
        i=self.motor.currentIndex();return self.motors[i] if 0<=i<len(self.motors) else {}
    def _guard(self):
        if self.transport.kind=="sim":return True
        if not self.unlock.isChecked():QMessageBox.warning(self,"未解锁","真实电机会动作。请先架空车辆并勾选“解锁电机实验”。");return False
        return True
    def _run(self,v,force=False):
        m=self._selected()
        if not m or (not force and not self._guard()):return
        if self.mode.currentText()=="PWM %":self.transport.command(m.get("key","motor"),v)
        else:self.transport.command(m.get("rpm_command_key",m.get("key","motor")+"_rpm_target"),v)
    def _send_pid(self):
        m=self._selected();prefix=m.get("pid_prefix",m.get("key","motor"))
        for k,sp in self.pid.items():self.transport.set_param(f"{prefix}_{k}",sp.value())
    def _encoder_check(self):
        if not self._guard():return
        m=self._selected();ek=m.get("encoder_key","");self.encoder_test={"motor":m,"start":float(self.last.get(ek,0)),"end":time.monotonic()+1.0};self.transport.command(m.get("key","motor"),15.0);self.result.setPlainText("编码器方向检查中：正向 15% 运行 1 秒...")
    def _tick(self):
        if not self.encoder_test or time.monotonic()<self.encoder_test["end"]:return
        t=self.encoder_test;self.encoder_test=None;m=t["motor"];self.transport.command(m.get("key","motor"),0);delta=float(self.last.get(m.get("encoder_key",""),0))-t["start"];expect=int(m.get("expected_encoder_sign",1) or 1);ok=delta*expect>0
        self.result.setPlainText(f"{m.get('label',m.get('key'))}: Encoder Δ={delta:.0f}，期望符号 {expect:+d}，结果：{'方向正确 ✓' if ok else '方向相反/无计数 ✗'}")
    def _tel(self,d):self.last.update(d);self._refresh()
    def _refresh(self):
        self.table.setRowCount(len(self.motors))
        for row,m in enumerate(self.motors):
            vals=[m.get("label",m.get("key","")),self.last.get(m.get("rpm_key",""),"--"),self.last.get(m.get("encoder_key",""),"--"),self.last.get(m.get("current_key",""),"--"),self.last.get(m.get("pwm_key",""),"--"),m.get("expected_encoder_sign",1),m.get("key","")]
            for col,v in enumerate(vals):self.table.setItem(row,col,QTableWidgetItem(str(v)))
