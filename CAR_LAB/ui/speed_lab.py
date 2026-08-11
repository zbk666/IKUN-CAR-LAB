
from collections import deque
import time, statistics
import pyqtgraph as pg
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget,QHBoxLayout,QVBoxLayout,QGridLayout,QGroupBox,QLabel,QPushButton,QDoubleSpinBox,QComboBox,QCheckBox,QPlainTextEdit,QFrame

class SpeedLab(QWidget):
    def __init__(self,bus,transport,config):
        super().__init__()
        self.bus=bus; self.transport=transport; self.cfg=config.get("speed_lab",{})
        self.t0=time.monotonic(); self.t=deque(maxlen=4000); self.series={k:deque(maxlen=4000) for k in ("target","actual","error","output")}
        self.last_tel=None; self.rx_intervals=deque(maxlen=100); self.auto_apply=True
        root=QHBoxLayout(self)
        left=QVBoxLayout()
        g=QGroupBox("速度目标"); grid=QGridLayout(g)
        self.target=QDoubleSpinBox(); self.target.setRange(-10000,10000); self.target.setDecimals(1); self.target.setValue(500)
        b=QPushButton("发送目标 RPM"); b.clicked.connect(lambda:self.transport.command(self.cfg.get("target_command_key","target_rpm"),self.target.value()))
        grid.addWidget(QLabel("目标 RPM"),0,0); grid.addWidget(self.target,0,1); grid.addWidget(b,1,0,1,2); left.addWidget(g)
        pgp=QGroupBox("在线 PID · 改完立即生效"); pid_grid=QGridLayout(pgp)
        self.step=QComboBox(); self.step.addItems(["0.001","0.01","0.1","1"]); self.step.setCurrentText("0.01"); self.step.currentTextChanged.connect(self._step)
        self.auto=QCheckBox("立即发送"); self.auto.setChecked(True)
        pid_grid.addWidget(QLabel("步长"),0,0); pid_grid.addWidget(self.step,0,1); pid_grid.addWidget(self.auto,0,2)
        self.spins={}
        params=self.cfg.get("params",{"Kp":"speed_kp","Ki":"speed_ki","Kd":"speed_kd"})
        defaults={"Kp":.85,"Ki":.1,"Kd":.01}
        for r,(label,key) in enumerate(params.items(),1):
            minus=QPushButton("−"); plus=QPushButton("+")
            sp=QDoubleSpinBox(); sp.setRange(-9999,9999); sp.setDecimals(5); sp.setValue(defaults.get(label,0))
            minus.clicked.connect(lambda _=False,s=sp:s.setValue(s.value()-s.singleStep()))
            plus.clicked.connect(lambda _=False,s=sp:s.setValue(s.value()+s.singleStep()))
            sp.valueChanged.connect(lambda _v,k=key,l=label,s=sp:self._send(k,l,s.value()) if self.auto.isChecked() else None)
            pid_grid.addWidget(QLabel(label),r,0); pid_grid.addWidget(minus,r,1); pid_grid.addWidget(sp,r,2); pid_grid.addWidget(plus,r,3); self.spins[label]=(sp,key)
        left.addWidget(pgp)
        self.sync=QLabel("参数状态：待命"); left.addWidget(self.sync)
        self.metrics=QLabel("当前：目标 -- | 实际 -- | 误差 -- | 输出 --"); self.metrics.setWordWrap(True); left.addWidget(self.metrics)
        self.log=QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumBlockCount(120); left.addWidget(self.log,1)
        root.addLayout(left,0)

        right=QVBoxLayout()
        self.p1=pg.PlotWidget(title="速度跟踪 · 目标 / 实际"); self.p1.showGrid(x=True,y=True,alpha=.18); self.p1.addLegend(); self.c_target=self.p1.plot(name="目标",pen=pg.mkPen((40,100,210),width=2)); self.c_actual=self.p1.plot(name="实际",pen=pg.mkPen((220,130,40),width=2))
        self.p2=pg.PlotWidget(title="误差（局部自动放大）"); self.p2.showGrid(x=True,y=True,alpha=.18); self.c_error=self.p2.plot(name="Error",pen=pg.mkPen((200,70,70),width=2))
        right.addWidget(self.p1,1); right.addWidget(self.p2,1); root.addLayout(right,1)

        bus.telemetry.connect(self._tel); bus.ack.connect(self._ack); bus.parameter_sync.connect(self._sync)
        timer=QTimer(self); timer.timeout.connect(self._draw); timer.start(50)

    def _step(self,text):
        v=float(text)
        for sp,_ in self.spins.values(): sp.setSingleStep(v)
    def _send(self,key,label,value):
        self.transport.set_param(key,value)
    def _sync(self,info):
        key=info.get("key")
        keys={k for _,k in self.spins.values()}
        if key not in keys:return
        state=info.get("state","")
        self.sync.setText(f"参数状态：{state} · {info.get('message','')}")
    def _ack(self,key,val):
        keys={k for _,k in self.spins.values()}
        if key in keys:self.log.appendPlainText(f"ACK {key} = {val}")
    def _tel(self,d):
        now=time.monotonic()
        if self.last_tel:self.rx_intervals.append(now-self.last_tel)
        self.last_tel=now
        t=now-self.t0; self.t.append(t)
        target=float(d.get(self.cfg.get("target_key","target_rpm"),0)); actual=float(d.get(self.cfg.get("actual_key","actual_rpm"),0))
        error=float(d.get(self.cfg.get("error_key","speed_error"),target-actual)); out=float(d.get(self.cfg.get("output_key","motor_pwm"),0))
        for k,v in [("target",target),("actual",actual),("error",error),("output",out)]: self.series[k].append(v)
        self.metrics.setText(f"当前：目标 {target:.1f} | 实际 {actual:.1f} | 误差 {error:.1f} | 输出 {out:.1f}")
    def _draw(self):
        x=list(self.t)
        if not x:return
        for curve,k in [(self.c_target,"target"),(self.c_actual,"actual"),(self.c_error,"error")]:
            y=list(self.series[k]); n=min(len(x),len(y)); curve.setData(x[-n:],y[-n:])
        vals=list(self.series["error"])[-400:]
        if vals:
            lo=min(vals); hi=max(vals); pad=max(0.5,(hi-lo)*.12)
            self.p2.setYRange(lo-pad,hi+pad,padding=0)
        right=x[-1]; self.p1.setXRange(max(0,right-20),right,padding=0); self.p2.setXRange(max(0,right-20),right,padding=0)
