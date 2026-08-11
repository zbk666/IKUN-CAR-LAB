
from collections import deque
import json, time
from pathlib import Path
import pyqtgraph as pg
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QWidget,QHBoxLayout,QVBoxLayout,QGridLayout,QGroupBox,QLabel,QPushButton,
    QDoubleSpinBox,QComboBox,QCheckBox,QLineEdit,QMessageBox,QPlainTextEdit
)

FIELD_LABELS = {
    "target_command_key": ("目标命令","Command"),
    "target_key": ("目标遥测","Target"),
    "feedback_key": ("反馈遥测","Feedback"),
    "error_key": ("误差遥测","Error"),
    "output_key": ("输出遥测","Output"),
}
class CustomLoopLab(QWidget):
    def __init__(self,bus,transport,config):
        super().__init__()
        self.bus=bus; self.transport=transport; self.config=config
        self.store_path=Path(__file__).resolve().parents[1]/"data"/"custom_loops.json"
        self.loops=list(config.get("pid_loops",[]) or [])+self._load_local_loops()
        if not self.loops:self.loops=[self._blank_loop()]
        self.current=dict(self.loops[0]); self.t0=time.monotonic(); self.t=deque(maxlen=3000)
        self.s={k:deque(maxlen=3000) for k in ("target","feedback","error","output")}
        self.expert_mode=False
        self._build(); self._fill_loop_combo(); self._load_loop(0)
        bus.telemetry.connect(self._tel); bus.ack.connect(self._ack); bus.parameter_sync.connect(self._sync)
        timer=QTimer(self); timer.timeout.connect(self._draw); timer.start(50)

    @staticmethod
    def _blank_loop():
        return {"key":"custom_loop_1","name":"自定义环1","unit":"","target_command_key":"custom_target","target_key":"custom_target","feedback_key":"custom_feedback","error_key":"custom_error","output_key":"custom_output","params":{"Kp":"custom_kp","Ki":"custom_ki","Kd":"custom_kd"}}

    def _load_local_loops(self):
        try:
            if self.store_path.exists():
                d=json.loads(self.store_path.read_text(encoding="utf-8"))
                return d if isinstance(d,list) else []
        except Exception: pass
        return []

    def _build(self):
        root=QHBoxLayout(self); left=QVBoxLayout(); left.setSpacing(8)
        mapping=QGroupBox("自定义环")
        g=QGridLayout(mapping)
        self.loop_combo=QComboBox(); self.loop_combo.currentIndexChanged.connect(self._load_loop)
        self.expert=QCheckBox("专家模式"); self.expert.stateChanged.connect(self._toggle_expert)
        g.addWidget(QLabel("控制环"),0,0); g.addWidget(self.loop_combo,0,1,1,2); g.addWidget(self.expert,0,3)

        # Simple mode fields
        self.simple_hint=QLabel("普通模式：只配置环的名称和单位，其余协议字段由专家模式设置。")
        self.simple_hint.setWordWrap(True); g.addWidget(self.simple_hint,1,0,1,4)

        names=[("名称","name"),("单位","unit"),("目标命令","target_command_key"),("目标遥测","target_key"),("反馈遥测","feedback_key"),("误差遥测","error_key"),("输出遥测","output_key"),("Kp Key","kp"),("Ki Key","ki"),("Kd Key","kd")]
        self.fields={}; self.expert_widgets=[]
        for i,(label,key) in enumerate(names,start=2):
            lab=QLabel(label); edit=QLineEdit(); self.fields[key]=edit
            g.addWidget(lab,i,0); g.addWidget(edit,i,1,1,3); self.expert_widgets += [lab,edit]
        apply_btn=QPushButton("应用映射"); apply_btn.clicked.connect(self._apply_mapping)
        save_btn=QPushButton("保存本地自定义环"); save_btn.clicked.connect(self._save_local)
        g.addWidget(apply_btn,len(names)+2,0,1,2); g.addWidget(save_btn,len(names)+2,2,1,2)
        left.addWidget(mapping)

        target_box=QGroupBox("目标 / 在线 PID")
        tg=QGridLayout(target_box)
        self.target=QDoubleSpinBox(); self.target.setRange(-1e9,1e9); self.target.setDecimals(4)
        send=QPushButton("发送目标"); send.clicked.connect(self._send_target)
        self.step=QComboBox(); self.step.addItems(["0.001","0.01","0.1","1","10"]); self.step.setCurrentText("0.01")
        self.auto=QCheckBox("修改后立即 SET"); self.auto.setChecked(True)
        tg.addWidget(QLabel("目标"),0,0); tg.addWidget(self.target,0,1); tg.addWidget(send,0,2)
        tg.addWidget(QLabel("步长"),1,0); tg.addWidget(self.step,1,1); tg.addWidget(self.auto,1,2)
        self.spins={}
        for r,label in enumerate(("Kp","Ki","Kd"),start=2):
            minus=QPushButton("−"); plus=QPushButton("+"); sp=QDoubleSpinBox(); sp.setRange(-99999,99999); sp.setDecimals(6); sp.setValue({"Kp":1.0,"Ki":0.0,"Kd":0.0}[label])
            minus.clicked.connect(lambda _=False,s=sp:s.setValue(s.value()-s.singleStep()))
            plus.clicked.connect(lambda _=False,s=sp:s.setValue(s.value()+s.singleStep()))
            sp.valueChanged.connect(lambda _v,l=label,s=sp:self._param_changed(l,s.value()) if self.auto.isChecked() else None)
            sp.editingFinished.connect(lambda l=label,s=sp:self._param_commit(l,s.value()) if not self.auto.isChecked() else None)
            tg.addWidget(QLabel(label),r,0); tg.addWidget(minus,r,1); tg.addWidget(sp,r,2); tg.addWidget(plus,r,3)
            self.spins[label]=sp
        self.step.currentTextChanged.connect(self._step_changed); self._step_changed(self.step.currentText())
        left.addWidget(target_box)
        self.status=QLabel("参数状态：待命"); self.status.setWordWrap(True); left.addWidget(self.status)
        self.log=QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumBlockCount(150); left.addWidget(self.log,1)
        root.addLayout(left,0)

        right=QVBoxLayout()
        self.p1=pg.PlotWidget(title="自定义环：目标 / 反馈 / 误差"); self.p1.showGrid(x=True,y=True,alpha=.18)
        self.c_t=self.p1.plot(name="目标",pen=pg.mkPen((45,108,210),width=2)); self.c_f=self.p1.plot(name="反馈",pen=pg.mkPen((220,135,40),width=2)); self.c_e=self.p1.plot(name="误差",pen=pg.mkPen((190,65,75),width=2))
        self.p2=pg.PlotWidget(title="自定义环：输出"); self.p2.showGrid(x=True,y=True,alpha=.18)
        self.c_o=self.p2.plot(name="输出",pen=pg.mkPen((40,155,100),width=2))
        right.addWidget(self.p1,1); right.addWidget(self.p2,1); root.addLayout(right,1)
        self._toggle_expert(0)

    def _toggle_expert(self,state):
        self.expert_mode=bool(state)
        visible=self.expert_mode
        for w in self.expert_widgets:w.setVisible(visible)
        self.simple_hint.setText("专家模式：直接编辑协议字段映射和 PID 参数 key。"
                                 if visible else "普通模式：用于日常调参；需要修改 MCU 字段映射时再打开专家模式。")

    def _fill_loop_combo(self):
        self.loop_combo.blockSignals(True); self.loop_combo.clear()
        for x in self.loops:self.loop_combo.addItem(str(x.get("name",x.get("key","自定义环"))))
        self.loop_combo.blockSignals(False)

    def _load_loop(self,index):
        if not (0<=index<len(self.loops)):return
        loop=dict(self.loops[index]); params=dict(loop.get("params",{}))
        self.fields["name"].setText(str(loop.get("name",""))); self.fields["unit"].setText(str(loop.get("unit","")))
        for k in ("target_command_key","target_key","feedback_key","error_key","output_key"): self.fields[k].setText(str(loop.get(k,"")))
        for k in ("kp","ki","kd"): self.fields[k].setText(str(params.get(k.upper(),"")))
        self._apply_mapping(clear=True)

    def _apply_mapping(self,clear=True):
        self.current={
            "key":self.current.get("key","custom_loop"),
            "name":self.fields["name"].text().strip() or "自定义环",
            "unit":self.fields["unit"].text().strip(),
            "target_command_key":self.fields["target_command_key"].text().strip(),
            "target_key":self.fields["target_key"].text().strip(),
            "feedback_key":self.fields["feedback_key"].text().strip(),
            "error_key":self.fields["error_key"].text().strip(),
            "output_key":self.fields["output_key"].text().strip(),
            "params":{"Kp":self.fields["kp"].text().strip(),"Ki":self.fields["ki"].text().strip(),"Kd":self.fields["kd"].text().strip()},
        }
        self.p1.setTitle(f"{self.current['name']}：目标 / 反馈 / 误差")
        self.p2.setTitle(f"{self.current['name']}：输出")
        if clear:self._clear_data()

    def _save_local(self):
        self._apply_mapping(False); local=self._load_local_loops(); item=dict(self.current); item["key"]=f"local_{int(time.time())}"
        local.append(item); self.store_path.parent.mkdir(parents=True,exist_ok=True); self.store_path.write_text(json.dumps(local,ensure_ascii=False,indent=2),encoding="utf-8")
        self.loops.append(item); self._fill_loop_combo(); self.loop_combo.setCurrentIndex(len(self.loops)-1)
        QMessageBox.information(self,"自定义环","已保存。")

    def _step_changed(self,text):
        st=float(text)
        for sp in self.spins.values():sp.setSingleStep(st)

    def _param_key(self,label):return str(self.current.get("params",{}).get(label,"")).strip()

    def _param_changed(self,label,value):
        key=self._param_key(label)
        if key:self.transport.set_param(key,value); self.status.setText(f"参数状态：{label} → {value:g}，进入缓冲区")

    def _param_commit(self,label,value):
        self._param_changed(label,value)

    def _send_target(self):
        key=str(self.current.get("target_command_key","")).strip()
        if key:self.transport.command(key,self.target.value())

    def _sync(self,info):
        key=str(info.get("key",""))
        watched=set(self.current.get("params",{}).values())
        if key in watched:self.status.setText(f"参数状态：{info.get('state')} · {info.get('message','')}")

    def _ack(self,key,value):
        watched=set(self.current.get("params",{}).values())|{self.current.get("target_command_key","")}
        if key in watched:self.log.appendPlainText(f"确认：{key} = {value}")

    def _tel(self,d):
        c=self.current; now=time.monotonic(); self.t.append(now-self.t0); self.latest=d
        def val(key,default=0.0):
            try:return float(d.get(key,default))
            except Exception:return default
        target=val(c.get("target_key")); feedback=val(c.get("feedback_key")); error=val(c.get("error_key"),target-feedback); output=val(c.get("output_key"))
        if not c.get("error_key"):error=target-feedback
        for k,v in (("target",target),("feedback",feedback),("error",error),("output",output)):self.s[k].append(v)
        unit=c.get("unit","");self.status.setText(f"参数状态：正常 · 目标 {target:.3f}{unit} · 反馈 {feedback:.3f}{unit} · 误差 {error:+.3f}{unit}")

    def _draw(self):
        x=list(self.t)
        if not x:return
        for c,k in ((self.c_t,"target"),(self.c_f,"feedback"),(self.c_e,"error"),(self.c_o,"output")):
            y=list(self.s[k]);n=min(len(x),len(y));c.setData(x[-n:],y[-n:])

    def _clear_data(self):
        self.t0=time.monotonic();self.t.clear()
        for q in self.s.values():q.clear()
