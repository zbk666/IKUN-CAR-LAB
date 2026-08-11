from collections import deque
import time
import pyqtgraph as pg
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QWidget,QHBoxLayout,QVBoxLayout,QGridLayout,QGroupBox,QLabel,QPushButton,
    QDoubleSpinBox,QComboBox,QCheckBox,QPlainTextEdit
)
from core.angle import angle_error_deg
from ui.plot_cursor import CurveInspector


class HeadingLab(QWidget):
    def __init__(self,bus,transport,config):
        super().__init__(); self.bus=bus; self.transport=transport; self.cfg=config.get("heading_lab",{})
        self.t0=time.monotonic(); self.t=deque(maxlen=2400)
        keys=("target_yaw","yaw","yaw_error","target_rate","rate","steer","speed")
        self.s={k:deque(maxlen=2400) for k in keys}; self.last={}; self.marker=[]
        root=QHBoxLayout(self); left=QVBoxLayout()

        target_box=QGroupBox("航向目标 / 角度阶跃")
        tg=QGridLayout(target_box)
        self.target=QDoubleSpinBox(); self.target.setRange(-180,180); self.target.setDecimals(1); self.target.setValue(30)
        send=QPushButton("发送目标航向"); send.clicked.connect(lambda:self.transport.command(self.cfg.get("target_command_key","target_yaw"),self.target.value()))
        zero=QPushButton("回到 0°"); zero.clicked.connect(lambda:self.transport.command(self.cfg.get("target_command_key","target_yaw"),0.0))
        tg.addWidget(QLabel("Target Yaw"),0,0); tg.addWidget(self.target,0,1); tg.addWidget(send,1,0); tg.addWidget(zero,1,1)
        left.addWidget(target_box)

        self.step=QComboBox(); self.step.addItems(["0.001","0.01","0.1","1"]); self.step.setCurrentText("0.01")
        self.auto=QCheckBox("修改立即 SET"); self.auto.setChecked(True)
        self.param_spins={}
        outer=self.cfg.get("outer_params",{"Kp":"heading_kp","Ki":"heading_ki","Kd":"heading_kd"})
        inner=self.cfg.get("inner_params",{"Kp":"yaw_rate_kp","Ki":"yaw_rate_ki","Kd":"yaw_rate_kd"})
        left.addWidget(self._pid_box("外环：Yaw / Heading",outer,{"Kp":2.4,"Ki":0,"Kd":0.12}))
        left.addWidget(self._pid_box("内环：Yaw Rate / Gyro Z",inner,{"Kp":0.85,"Ki":0.06,"Kd":0.01}))
        self.step.currentTextChanged.connect(self._step_changed); self._step_changed(self.step.currentText())

        settings=QGroupBox("在线调参设置"); sg=QHBoxLayout(settings); sg.addWidget(QLabel("步长")); sg.addWidget(self.step); sg.addWidget(self.auto)
        left.addWidget(settings)
        self.metrics=QLabel("Yaw Error -- | Rate Error -- | Speed --")
        left.addWidget(self.metrics)
        self.diag=QPlainTextEdit(); self.diag.setReadOnly(True); self.diag.setMaximumHeight(170)
        self.diag.setPlainText("角度环诊断会同时观察：角度误差、目标角速度、实际角速度、转向输出和车速。")
        left.addWidget(self.diag)
        root.addLayout(left,0)

        right=QVBoxLayout()
        self.p_yaw=pg.PlotWidget(title="Heading Outer Loop: Target Yaw / Actual Yaw / Error")
        self.p_yaw.setBackground((10,15,22)); self.p_yaw.showGrid(x=True,y=True,alpha=.18); self.p_yaw.addLegend(); self.p_yaw.setLabel("bottom","Time",units="s"); self.p_yaw.setLabel("left","Yaw",units="deg")
        self.cy_t=self.p_yaw.plot(name="Target Yaw",pen=pg.mkPen((88,166,255),width=2)); self.cy_a=self.p_yaw.plot(name="Actual Yaw",pen=pg.mkPen((255,184,77),width=2)); self.cy_e=self.p_yaw.plot(name="Yaw Error",pen=pg.mkPen((255,107,107),width=2))
        self.p_rate=pg.PlotWidget(title="Yaw Rate Inner Loop: Target Rate / Gyro Z / Steering")
        self.p_rate.setBackground((10,15,22)); self.p_rate.showGrid(x=True,y=True,alpha=.18); self.p_rate.addLegend(); self.p_rate.setLabel("bottom","Time",units="s")
        self.cr_t=self.p_rate.plot(name="Target Yaw Rate",pen=pg.mkPen((88,166,255),width=2)); self.cr_a=self.p_rate.plot(name="Gyro Z",pen=pg.mkPen((90,214,142),width=2)); self.cr_s=self.p_rate.plot(name="Steering Output",pen=pg.mkPen((187,134,252),width=2))
        right.addWidget(self.p_yaw,1); right.addWidget(self.p_rate,1); root.addLayout(right,1)
        self.inspect_yaw=CurveInspector(self.p_yaw, lambda:(list(self.t), {"Target Yaw":list(self.s["target_yaw"]),"Yaw":list(self.s["yaw"]),"Yaw Error":list(self.s["yaw_error"])}))
        self.inspect_rate=CurveInspector(self.p_rate, lambda:(list(self.t), {"Target Rate":list(self.s["target_rate"]),"Gyro Z":list(self.s["rate"]),"Steering":list(self.s["steer"])}))
        bus.telemetry.connect(self._tel); bus.parameter_changed.connect(self._mark)
        timer=QTimer(self); timer.timeout.connect(self._draw); timer.start(50)
        dtimer=QTimer(self); dtimer.timeout.connect(self._diagnose); dtimer.start(700)

    def _pid_box(self,title,params,defaults):
        box=QGroupBox(title); g=QGridLayout(box)
        for r,(label,key) in enumerate(params.items()):
            sp=QDoubleSpinBox(); sp.setRange(-9999,9999); sp.setDecimals(5); sp.setValue(defaults.get(label,0)); sp.setSingleStep(.01)
            minus=QPushButton("−"); plus=QPushButton("+"); minus.setFixedWidth(35); plus.setFixedWidth(35)
            minus.clicked.connect(lambda _=False,s=sp:s.setValue(s.value()-s.singleStep()))
            plus.clicked.connect(lambda _=False,s=sp:s.setValue(s.value()+s.singleStep()))
            sp.valueChanged.connect(lambda _v,s=sp,k=key:self.transport.set_param(k,s.value()) if self.auto.isChecked() else None)
            sp.editingFinished.connect(lambda s=sp,k=key:self.transport.set_param(k,s.value()) if not self.auto.isChecked() else None)
            g.addWidget(QLabel(label),r,0); g.addWidget(minus,r,1); g.addWidget(sp,r,2); g.addWidget(plus,r,3)
            self.param_spins[key]=sp
        return box
    def _step_changed(self,text):
        st=float(text)
        for sp in self.param_spins.values(): sp.setSingleStep(st)
    def _mark(self,key,old,new):
        if key not in self.param_spins:return
        x=time.monotonic()-self.t0
        line=pg.InfiniteLine(pos=x,angle=90,label=f"{key}: {old}→{new}",labelOpts={"position":0.9})
        self.p_yaw.addItem(line); self.marker.append(line)
        if len(self.marker)>20:
            o=self.marker.pop(0); self.p_yaw.removeItem(o)
    def _tel(self,d):
        self.last=d; now=time.monotonic(); self.t.append(now-self.t0)
        c=self.cfg
        ty=float(d.get(c.get("target_yaw_key","target_yaw"),0)); yaw=float(d.get(c.get("yaw_key","yaw"),0))
        ye=float(d.get(c.get("yaw_error_key","yaw_error"),angle_error_deg(ty,yaw)))
        tr=float(d.get(c.get("target_yaw_rate_key","target_yaw_rate"),0)); rate=float(d.get(c.get("yaw_rate_key","gyro_z"),0))
        steer=float(d.get(c.get("steering_key","steering_output"),0)); speed=float(d.get(c.get("speed_key","speed"),0))
        for k,v in (("target_yaw",ty),("yaw",yaw),("yaw_error",ye),("target_rate",tr),("rate",rate),("steer",steer),("speed",speed)):self.s[k].append(v)
        self.metrics.setText(f"Yaw Error {ye:+.2f}° | Rate Error {tr-rate:+.2f}°/s | Speed {speed:.2f} m/s | Steer {steer:+.1f}%")
    def _draw(self):
        x=list(self.t)
        if not x:return
        mapping=((self.cy_t,"target_yaw"),(self.cy_a,"yaw"),(self.cy_e,"yaw_error"),(self.cr_t,"target_rate"),(self.cr_a,"rate"),(self.cr_s,"steer"))
        for c,k in mapping:
            y=list(self.s[k]); n=min(len(x),len(y)); c.setData(x[-n:],y[-n:])
    def _diagnose(self):
        if len(self.s["yaw_error"])<30:return
        err=list(self.s["yaw_error"])[-80:]; tr=list(self.s["target_rate"])[-80:]; ar=list(self.s["rate"])[-80:]; speed=list(self.s["speed"])[-80:]
        mae=sum(abs(x) for x in err)/len(err); rate_mae=sum(abs(a-b) for a,b in zip(tr,ar))/len(tr); avg_speed=sum(abs(x) for x in speed)/len(speed)
        crossings=sum(1 for a,b in zip(err,err[1:]) if a*b<0 and abs(a-b)>1.0)
        msgs=[]
        if rate_mae>20 and mae>4: msgs.append("内环角速度跟随不足：先调 Yaw Rate 内环，不要急着继续增大外环 Kp。")
        if crossings>=4: msgs.append("航向误差反复过零，存在摆动趋势：外环可能偏激进，或内环阻尼不足。")
        if avg_speed>2.5 and crossings>=2: msgs.append("高速下摆动更明显：建议按车速分组验证 Heading 参数，必要时做 gain scheduling。")
        if mae<2 and rate_mae<12: msgs.append("当前角度/角速度跟随较稳定，可继续做不同速度下的角度阶跃测试。")
        if not msgs: msgs.append("继续观察 Target Yaw、Yaw、Target Rate、Gyro Z 和 Steering 的相互关系。")
        self.diag.setPlainText("本地诊断（规则分析）\n"+"\n".join("• "+m for m in msgs)+f"\n\n近窗 MAE: yaw={mae:.2f}°, rate={rate_mae:.2f}°/s, speed={avg_speed:.2f}m/s")
