from collections import deque
import time
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget,QVBoxLayout,QGridLayout,QGroupBox,QLabel,QPlainTextEdit,QPushButton
from core.config import validate_vehicle_config

class DiagnosticsPage(QWidget):
    def __init__(self,bus,transport,config):
        super().__init__()
        self.bus=bus; self.transport=transport; self.last_tel=None; self.tel_intervals=deque(maxlen=200)
        self.rx=0; self.tx=0; self.protocol_errors=0
        self.config_issues=validate_vehicle_config(config); self.param_events=deque(maxlen=100)
        root=QVBoxLayout(self)
        box=QGroupBox("实时通信诊断"); g=QGridLayout(box)
        self.conn=QLabel("未连接"); self.rate=QLabel("-- Hz"); self.age=QLabel("-- ms")
        self.counts=QLabel("RX 0 / TX 0"); self.err=QLabel("协议错误 0")
        for i,(name,w) in enumerate((("连接状态",self.conn),("TEL 频率",self.rate),("最近遥测",self.age),("收发计数",self.counts),("协议错误",self.err))):
            g.addWidget(QLabel(name),i,0); g.addWidget(w,i,1)
        root.addWidget(box)
        self.advice=QPlainTextEdit(); self.advice.setReadOnly(True); root.addWidget(self.advice,1)
        clear=QPushButton("清空诊断计数"); clear.clicked.connect(self._clear); root.addWidget(clear)
        bus.connection.connect(self._connection); bus.telemetry.connect(self._tel); bus.rx_text.connect(self._rx)
        bus.tx_text.connect(self._tx); bus.event.connect(self._event); bus.parameter_sync.connect(self._param_sync)
        timer=QTimer(self); timer.timeout.connect(self._update); timer.start(500)

    def _connection(self,ok,text): self.conn.setText(text)
    def _tel(self,_d):
        now=time.monotonic()
        if self.last_tel is not None:self.tel_intervals.append(now-self.last_tel)
        self.last_tel=now
    def _rx(self,_): self.rx+=1
    def _tx(self,_): self.tx+=1
    def _event(self,typ,_data):
        if typ=="protocol_error": self.protocol_errors+=1
    def _param_sync(self,info): self.param_events.append(dict(info))
    def _clear(self):
        self.rx=self.tx=self.protocol_errors=0; self.tel_intervals.clear(); self.param_events.clear()
    def _update(self):
        hz=1/(sum(self.tel_intervals)/len(self.tel_intervals)) if self.tel_intervals else 0
        age=(time.monotonic()-self.last_tel)*1000 if self.last_tel else 999999
        self.rate.setText(f"{hz:.1f} Hz")
        self.age.setText("--" if not self.last_tel else f"{age:.0f} ms")
        self.counts.setText(f"RX {self.rx} / TX {self.tx}")
        self.err.setText(f"协议错误 {self.protocol_errors}")
        tips=[]
        if self.transport.connected and age>500: tips.append("已连接但超过 500ms 没有 TEL。")
        if 0<hz<20: tips.append("遥测低于 20Hz，实时 PID 曲线会明显变迟钝。")
        if hz>250: tips.append("遥测高于 250Hz，JSON 串口可能成为带宽瓶颈。")
        if self.protocol_errors: tips.append("存在协议解析错误，请查看协议监视器。")
        errors=[x["message"] for x in self.config_issues if x["severity"]=="error"]
        warns=[x["message"] for x in self.config_issues if x["severity"]!="error"]
        if errors: tips.append("参数冲突："+ "；".join(errors[:3]))
        elif warns: tips.append("参数配置提示："+ "；".join(warns[:3]))
        active=[x for x in self.param_events if x.get("state") in ("queued","sending","retry","timeout","deferred")]
        if active: tips.append(f"最近仍有 {len(active)} 条参数操作未最终确认。")
        if not tips: tips.append("通信与参数状态目前没有明显异常。")
        self.advice.setPlainText("本地诊断\n" + "\n".join("• "+x for x in tips))
