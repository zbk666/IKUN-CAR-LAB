
from collections import deque
import time
import math
import pyqtgraph as pg
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QLineEdit, QComboBox, QCheckBox, QDoubleSpinBox, QFrame
)

CHANNEL_NAMES = {
    "target_rpm": ("目标转速", "Target RPM"),
    "actual_rpm": ("实际转速", "Actual RPM"),
    "speed_error": ("速度误差", "Speed Error"),
    "motor_pwm": ("电机 PWM", "Motor PWM"),
    "left_rpm": ("左轮转速", "Left RPM"),
    "right_rpm": ("右轮转速", "Right RPM"),
    "left_pwm": ("左轮 PWM", "Left PWM"),
    "right_pwm": ("右轮 PWM", "Right PWM"),
    "left_encoder": ("左编码器", "Left Encoder"),
    "right_encoder": ("右编码器", "Right Encoder"),
    "target_yaw": ("目标航向角", "Target Yaw"),
    "yaw": ("实际航向角", "Yaw"),
    "yaw_error": ("航向角误差", "Yaw Error"),
    "target_yaw_rate": ("目标角速度", "Target Yaw Rate"),
    "gyro_z": ("横摆角速度", "Gyro Z"),
    "steering_output": ("转向输出", "Steering Output"),
    "speed": ("车速", "Speed"),
    "battery": ("电池电压", "Battery"),
    "battery_raw": ("ADC 原始值", "Battery ADC"),
    "left_current": ("左电机电流", "Left Current"),
    "right_current": ("右电机电流", "Right Current"),
    "tracking_error": ("循迹误差", "Tracking Error"),
    "curvature": ("赛道曲率", "Curvature"),
    "track_progress": ("赛道进度", "Track Progress"),
    "lap_trigger": ("计圈触发", "Lap Trigger"),
    "custom_target": ("自定义目标", "Custom Target"),
    "custom_feedback": ("自定义反馈", "Custom Feedback"),
    "custom_error": ("自定义误差", "Custom Error"),
    "custom_output": ("自定义输出", "Custom Output"),
    # 麦克纳姆轮全向底盘：运动解算 + 四轮
    "target_vx": ("目标 Vx", "Target Vx"),
    "vx": ("实际 Vx", "Vx"),
    "target_vy": ("目标 Vy", "Target Vy"),
    "vy": ("实际 Vy", "Vy"),
    "target_wz": ("目标 Wz", "Target Wz"),
    "wz": ("实际 Wz", "Wz"),
    "vx_output": ("Vx 输出", "Vx Output"),
    "vy_output": ("Vy 输出", "Vy Output"),
    "wz_output": ("Wz 输出", "Wz Output"),
    "fl_rpm": ("左前轮 RPM", "FL RPM"),
    "fr_rpm": ("右前轮 RPM", "FR RPM"),
    "rl_rpm": ("左后轮 RPM", "RL RPM"),
    "rr_rpm": ("右后轮 RPM", "RR RPM"),
    "fl_pwm": ("左前轮 PWM", "FL PWM"),
    "fr_pwm": ("右前轮 PWM", "FR PWM"),
    "rl_pwm": ("左后轮 PWM", "RL PWM"),
    "rr_pwm": ("右后轮 PWM", "RR PWM"),
    "fl_current": ("左前轮电流", "FL Current"),
    "fr_current": ("右前轮电流", "FR Current"),
    "rl_current": ("左后轮电流", "RL Current"),
    "rr_current": ("右后轮电流", "RR Current"),
}

PRESETS = {
    "速度": ["target_rpm","actual_rpm","speed_error","motor_pwm"],
    "航向": ["target_yaw","yaw","yaw_error"],
    "角速度": ["target_yaw_rate","gyro_z","steering_output"],
    "电源": ["battery","battery_raw","left_current","right_current"],
    "电机": ["left_rpm","right_rpm","left_pwm","right_pwm"],
    "循迹": ["speed","tracking_error","curvature","gyro_z"],
    # 麦轮专属工作组：目标/实际 Vx/Vy/Wz + 四轮 RPM/PWM + 电流，一键选通道。
    "麦轮运动": ["target_vx","vx","target_vy","vy","target_wz","wz",
              "fl_rpm","fr_rpm","rl_rpm","rr_rpm",
              "fl_pwm","fr_pwm","rl_pwm","rr_pwm",
              "fl_current","fr_current","rl_current","rr_current"],
}

def channel_name(key):
    label, _ = CHANNEL_NAMES.get(key, (key, key))
    return label

def channel_tip(key):
    label, en = CHANNEL_NAMES.get(key, (key, key))
    return f"{label}\n{en}\n协议字段：{key}"

class ScopePage(QWidget):
    def __init__(self,bus,config):
        super().__init__()
        self.bus=bus; self.config=config
        # 车型可在 YAML 里用 channel_names / scope_presets 扩展中文通道名与工作组，与内置合并。
        self.channel_names=dict(CHANNEL_NAMES)
        for k,v in (config.get("channel_names",{}) or {}).items():
            if isinstance(v,(list,tuple)):
                self.channel_names[str(k)]=(str(v[0]), str(v[1]) if len(v)>1 else str(v[0]))
            else:
                self.channel_names[str(k)]=(str(v), str(k))
        self.presets=dict(PRESETS)
        for name,keys in (config.get("scope_presets",{}) or {}).items():
            if isinstance(keys,(list,tuple)):
                self.presets[str(name)]=[str(x) for x in keys]
        self.default_preset=next(iter(config.get("scope_presets",{}) or {}), "速度")
        self.window_s=20.0; self.auto_y=True; self.scale_mode="局部"
        self.t=deque(maxlen=6000); self.data={}; self.channels=[]
        self.t0=time.monotonic(); self.freeze=False
        self.cursor_a=None; self.cursor_b=None; self.overlay_lines=[]
        root=QVBoxLayout(self); root.setContentsMargins(8,8,8,8); root.setSpacing(8)

        top=QHBoxLayout()
        self.preset=QComboBox(); self.preset.addItems(list(self.presets.keys())); self.preset.currentTextChanged.connect(self.apply_preset)
        top.addWidget(QLabel("工作组")); top.addWidget(self.preset)
        self.search=QLineEdit(); self.search.setPlaceholderText("搜索通道"); self.search.textChanged.connect(self.filter_channels); top.addWidget(self.search,1)
        self.freeze_btn=QPushButton("冻结"); self.freeze_btn.clicked.connect(self.toggle_freeze); top.addWidget(self.freeze_btn)
        self.follow_btn=QPushButton("跟随最新"); self.follow_btn.clicked.connect(self.follow_latest); top.addWidget(self.follow_btn)
        top.addWidget(QLabel("时间窗"))
        self.window=QDoubleSpinBox(); self.window.setRange(2,300); self.window.setValue(20); self.window.setSuffix(" s"); self.window.valueChanged.connect(lambda v:setattr(self,"window_s",float(v))); top.addWidget(self.window)
        self.y_mode=QComboBox(); self.y_mode.addItems(["局部","全范围","固定"]); self.y_mode.currentTextChanged.connect(self._y_mode_changed)
        top.addWidget(QLabel("Y轴")); top.addWidget(self.y_mode)
        root.addLayout(top)

        split=QHBoxLayout()
        left=QFrame(); left.setObjectName("panel"); ll=QVBoxLayout(left); ll.addWidget(QLabel("通道"))
        self.list=QListWidget(); self.list.itemChanged.connect(lambda _item:self._draw()); ll.addWidget(self.list,1)
        split.addWidget(left,0)

        center=QVBoxLayout()
        self.plot=pg.PlotWidget(title="实时示波器")
        self.plot.showGrid(x=True,y=True,alpha=.18); self.plot.addLegend(); self.plot.setLabel("bottom","时间",units="s")
        self.plot.setLabel("left","数值")
        self.plot.scene().sigMouseMoved.connect(self._mouse_moved)
        self.plot.scene().sigMouseClicked.connect(self._mouse_clicked)
        center.addWidget(self.plot,1)
        buttons=QHBoxLayout()
        for text,fn in [("清除 A/B",self.clear_ab_cursor),("局部放大",self.local_view),("重置视图",self.reset_view)]:
            b=QPushButton(text); b.clicked.connect(fn); buttons.addWidget(b)
        buttons.addStretch()
        center.addLayout(buttons); split.addLayout(center,1)

        right=QFrame(); right.setObjectName("panel"); rl=QVBoxLayout(right)
        rl.addWidget(QLabel("数据探针"))
        self.probe=QLabel("把鼠标移动到曲线上即可读取"); self.probe.setAlignment(Qt.AlignmentFlag.AlignTop|Qt.AlignmentFlag.AlignLeft); self.probe.setWordWrap(True); rl.addWidget(self.probe)
        self.cursor_info=QLabel("A/B：未锁定"); self.cursor_info.setWordWrap(True); rl.addWidget(self.cursor_info)
        self.status=QLabel("RX -- Hz"); self.status.setObjectName("muted"); rl.addStretch(); rl.addWidget(self.status)
        split.addWidget(right,0)
        root.addLayout(split,1)

        bus.telemetry.connect(self._tel)
        timer=QTimer(self); timer.timeout.connect(self._draw); timer.start(50)
        self.preset.blockSignals(True); self.preset.setCurrentText(self.default_preset); self.preset.blockSignals(False)
        self.apply_preset(self.default_preset)

    def _cname(self,key):
        label,_=self.channel_names.get(key,(key,key)); return label

    def _ctip(self,key):
        label,en=self.channel_names.get(key,(key,key)); return f"{label}\n{en}\n协议字段：{key}"

    def apply_preset(self,name):
        keys=self.presets.get(name,[])
        for k in keys:
            if k not in self.channels: self.channels.append(k)
        self._rebuild_list(keys)

    def _rebuild_list(self,checked=()):
        checked=set(checked)
        self.list.blockSignals(True); self.list.clear()
        for k in self.channels:
            item=QListWidgetItem(self._cname(k))
            item.setData(Qt.ItemDataRole.UserRole,k)
            item.setToolTip(self._ctip(k))
            item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if k in checked else Qt.CheckState.Unchecked)
            self.list.addItem(item)
        self.list.blockSignals(False)

    def filter_channels(self,text):
        t=text.lower().strip()
        for i in range(self.list.count()):
            item=self.list.item(i)
            item.setHidden(t not in item.text().lower() and t not in str(item.data(Qt.ItemDataRole.UserRole)).lower())

    def _selected(self):
        return [str(self.list.item(i).data(Qt.ItemDataRole.UserRole))
                for i in range(self.list.count()) if self.list.item(i).checkState()==Qt.CheckState.Checked]

    def _tel(self,d):
        if not d:return
        now=time.monotonic()-self.t0; self.t.append(now)
        for k,v in d.items():
            if isinstance(v,(int,float)):
                if k not in self.channels:
                    self.channels.append(k)
                    self._rebuild_list(self._selected())
                self.data.setdefault(k,deque(maxlen=6000)).append(float(v))
        self.status.setText(f"实时接收 · {len(d)} 个字段")

    def _times_values(self,k):
        vals=list(self.data.get(k,[])); ts=list(self.t); n=min(len(vals),len(ts))
        return ts[-n:], vals[-n:]

    def _draw(self):
        if self.freeze:return
        self.plot.clear(); self.plot.addLegend()
        palette=[(45,108,210),(220,135,40),(190,65,75),(40,155,100),(125,80,180),(40,155,165)]
        selected=self._selected(); all_vals=[]
        for i,k in enumerate(selected):
            x,y=self._times_values(k)
            if not x:continue
            self.plot.plot(x,y,name=self._cname(k),pen=pg.mkPen(palette[i%len(palette)],width=2))
            all_vals.extend(y[-1500:])
        if self.auto_y and all_vals:
            lo=min(all_vals); hi=max(all_vals)
            if self.scale_mode=="局部":
                vals=all_vals[-400:] if len(all_vals)>400 else all_vals; lo=min(vals); hi=max(vals); pad=max(.5,(hi-lo)*.12)
            elif self.scale_mode=="全范围":
                pad=max(1,(hi-lo)*.05)
            else:
                lo,hi=-100,100; pad=0
            if hi-lo<1e-9: lo-=1; hi+=1
            self.plot.setYRange(lo-pad,hi+pad,padding=0)
        if self.t:
            right=self.t[-1]; self.plot.setXRange(max(0,right-self.window_s),right,padding=0)
        self._draw_cursors()

    def _remove_overlays(self):
        for line in self.overlay_lines:
            try:self.plot.removeItem(line)
            except Exception:pass
        self.overlay_lines=[]

    def _draw_cursors(self):
        self._remove_overlays()
        for x,color in ((self.cursor_a,(60,100,180)),(self.cursor_b,(190,80,80))):
            if x is not None:
                line=pg.InfiniteLine(pos=x,angle=90,movable=False,pen=pg.mkPen(color,width=1))
                self.plot.addItem(line,ignoreBounds=True); self.overlay_lines.append(line)

    def _nearest_index(self,seq,target):
        return min(range(len(seq)),key=lambda i:abs(seq[i]-target)) if seq else None

    def _update_probe(self,x):
        lines=[f"时间：{x:.3f} s"]
        for k in self._selected():
            ts,ys=self._times_values(k); i=self._nearest_index(ts,x)
            if i is not None: lines.append(f"{self._cname(k)}：{ys[i]:.5g}  ({k})")
        self.probe.setText("\n".join(lines))
        if self.cursor_a is not None and self.cursor_b is not None:
            extra=[f"A = {self.cursor_a:.3f} s","B = {self.cursor_b:.3f} s",f"Δt = {abs(self.cursor_b-self.cursor_a):.3f} s"]
            for k in self._selected():
                ts,ys=self._times_values(k)
                ia=self._nearest_index(ts,self.cursor_a); ib=self._nearest_index(ts,self.cursor_b)
                if ia is not None and ib is not None:
                    extra.append(f"{self._cname(k)}：Δ {ys[ib]-ys[ia]:+.5g}")
            self.cursor_info.setText("\n".join(extra))
        else:
            self.cursor_info.setText("A/B：左键依次点击曲线锁定")

    def _mouse_moved(self,pos):
        if not self.plot.sceneBoundingRect().contains(pos): return
        point=self.plot.plotItem.vb.mapSceneToView(pos)
        self._update_probe(float(point.x()))

    def _mouse_clicked(self,ev):
        if ev.button()!=Qt.MouseButton.LeftButton:return
        point=self.plot.plotItem.vb.mapSceneToView(ev.scenePos()); x=float(point.x())
        if self.cursor_a is None:self.cursor_a=x
        elif self.cursor_b is None:self.cursor_b=x
        else:self.cursor_a=x; self.cursor_b=None
        self._draw()

    def clear_ab_cursor(self):
        self.cursor_a=None; self.cursor_b=None; self._draw()

    def toggle_freeze(self):
        self.freeze=not self.freeze; self.freeze_btn.setText("继续" if self.freeze else "冻结")

    def follow_latest(self):
        if self.t:
            right=self.t[-1]; self.plot.setXRange(max(0,right-self.window_s),right,padding=0)

    def local_view(self):
        vals=[]
        for k in self._selected():
            _,ys=self._times_values(k); vals.extend(ys[-400:])
        if vals:
            lo=min(vals); hi=max(vals); pad=max(.1,(hi-lo)*.08)
            self.plot.setYRange(lo-pad,hi+pad,padding=0)

    def reset_view(self):
        self.plot.enableAutoRange(axis=pg.ViewBox.YAxis)
        self.follow_latest()

    def _y_mode_changed(self,text):
        self.scale_mode=text
