from collections import deque
import time
import pyqtgraph as pg
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QGroupBox,QLabel


class PowerMonitor(QWidget):
    def __init__(self,bus,config):
        super().__init__(); self.cfg=config.get("power_monitor",{}); self.t0=time.monotonic(); self.t=deque(maxlen=1800)
        self.v=deque(maxlen=1800); self.li=deque(maxlen=1800); self.ri=deque(maxlen=1800); self.min_v=None; self.max_v=None
        root=QVBoxLayout(self)
        cards=QGroupBox("电源状态"); g=QGridLayout(cards)
        self.bat=QLabel("-- V"); self.bat.setStyleSheet("font-size:34px;font-weight:700")
        self.raw=QLabel("ADC RAW --"); self.left=QLabel("左电流 -- A"); self.right=QLabel("右电流 -- A")
        self.sag=QLabel("压降 -- V"); self.state=QLabel("状态：等待数据")
        for i,w in enumerate((self.bat,self.raw,self.left,self.right,self.sag,self.state)):g.addWidget(w,i//3,i%3)
        root.addWidget(cards)
        self.plot=pg.PlotWidget(title="电池电压 / 电机电流"); self.plot.showGrid(x=True,y=True,alpha=.2); self.plot.addLegend()
        self.cv=self.plot.plot(name="电池电压 V",pen=pg.mkPen((88,166,255),width=2)); self.cl=self.plot.plot(name="左电流 A",pen=pg.mkPen((90,214,142),width=2)); self.cr=self.plot.plot(name="右电流 A",pen=pg.mkPen((255,184,77),width=2))
        root.addWidget(self.plot,1)
        hint=QLabel("ADC 必须在 MCU 端真实采样。CAR LAB 只负责接收 battery / battery_raw / left_current / right_current。\n分压比、ADC 位数、Vref、校准系数请在车型 YAML 与 MCU ADC 模块中保持一致。")
        hint.setWordWrap(True); root.addWidget(hint)
        bus.telemetry.connect(self._tel)
        timer=QTimer(self); timer.timeout.connect(self._draw); timer.start(100)
    def _tel(self,d):
        c=self.cfg; bk=c.get("battery_key","battery"); rk=c.get("raw_key","battery_raw"); lk=c.get("left_current_key","left_current"); rr=c.get("right_current_key","right_current")
        if bk not in d:return
        v=float(d[bk]); li=float(d.get(lk,0)); ri=float(d.get(rr,0)); self.t.append(time.monotonic()-self.t0); self.v.append(v); self.li.append(li); self.ri.append(ri)
        self.min_v=v if self.min_v is None else min(self.min_v,v); self.max_v=v if self.max_v is None else max(self.max_v,v)
        self.bat.setText(f"{v:.2f} V"); self.raw.setText(f"ADC RAW {d.get(rk,'--')}"); self.left.setText(f"左电流 {li:.2f} A"); self.right.setText(f"右电流 {ri:.2f} A")
        self.sag.setText(f"压降 {(self.max_v-v):.2f} V | 最低 {self.min_v:.2f} V")
        warn=float(c.get("warning_voltage",10.8)); crit=float(c.get("critical_voltage",10.2))
        if v<=crit: txt="状态：CRITICAL 低电压"; css="color:#ff4d4f;font-weight:700"
        elif v<=warn: txt="状态：WARNING 电压偏低"; css="color:#f2c94c;font-weight:700"
        else: txt="状态：NORMAL"; css="color:#7ee787;font-weight:700"
        self.state.setText(txt); self.state.setStyleSheet(css)
    def _draw(self):
        x=list(self.t)
        if not x:return
        for c,y in ((self.cv,self.v),(self.cl,self.li),(self.cr,self.ri)):
            yy=list(y);n=min(len(x),len(yy));c.setData(x[-n:],yy[-n:])
