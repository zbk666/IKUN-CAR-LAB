from __future__ import annotations
import time
from collections import deque
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QGroupBox,QLabel,QPushButton,QDoubleSpinBox,QPlainTextEdit,QCheckBox,QMessageBox
from core.metrics import response_metrics, score_speed_metrics
from core.history_store import HistoryStore


class AITunerPage(QWidget):
    """Local explainable tuning helper. It never calls a cloud model."""
    def __init__(self,bus,transport,config):
        super().__init__(); self.bus=bus;self.transport=transport;self.config=config;self.cfg=config.get("speed_lab",{});self.samples=deque(maxlen=3000);self.running=False;self.started=0;self.store=HistoryStore()
        root=QVBoxLayout(self)
        box=QGroupBox("速度环阶跃分析 / 本地 AI 建议");g=QGridLayout(box)
        self.target=QDoubleSpinBox();self.target.setRange(-10000,10000);self.target.setValue(500);self.seconds=QDoubleSpinBox();self.seconds.setRange(.5,15);self.seconds.setValue(3.0);self.unlock=QCheckBox("我已确认实车已架空/安全，允许发送阶跃目标")
        start=QPushButton("开始一次阶跃分析");start.clicked.connect(self._start);stop=QPushButton("立即停止");stop.clicked.connect(self._stop)
        g.addWidget(QLabel("目标 RPM"),0,0);g.addWidget(self.target,0,1);g.addWidget(QLabel("采集(s)"),0,2);g.addWidget(self.seconds,0,3);g.addWidget(self.unlock,1,0,1,4);g.addWidget(start,2,0,1,2);g.addWidget(stop,2,2,1,2);root.addWidget(box)
        self.out=QPlainTextEdit();self.out.setReadOnly(True);root.addWidget(self.out,1)
        bus.telemetry.connect(self._tel);self.timer=QTimer(self);self.timer.timeout.connect(self._tick);self.timer.start(50)
    def _start(self):
        if self.transport.kind!="sim" and not self.unlock.isChecked():
            QMessageBox.warning(self,"安全确认","实车阶跃会让电机动作。请先架空车辆并勾选安全确认。") ;return
        self.samples.clear();self.running=True;self.started=time.monotonic();self.transport.command(self.cfg.get("target_command_key","target_rpm"),self.target.value());self.out.setPlainText("采集中...\n当前功能是本地规则/指标分析，不连接云端 AI。")
    def _stop(self):
        self.transport.command(self.cfg.get("target_command_key","target_rpm"),0.0);self.running=False
    def _tel(self,d):
        if not self.running:return
        now=time.monotonic()-self.started;tk=self.cfg.get("target_key","target_rpm");ak=self.cfg.get("actual_key","actual_rpm")
        self.samples.append({"t":now,"target":float(d.get(tk,self.target.value())),"actual":float(d.get(ak,0)),"output":float(d.get(self.cfg.get("output_key","motor_pwm"),0))})
    def _tick(self):
        if not self.running or time.monotonic()-self.started<self.seconds.value():return
        self.running=False; self.transport.command(self.cfg.get("target_command_key","target_rpm"),0.0)
        sm=list(self.samples);m=response_metrics(sm);score=score_speed_metrics(m);p=dict(self.transport.param_cache)
        suggestions=[]
        ov=float(m.get("overshoot_pct",0));rise=m.get("rise_time_s");steady=float(m.get("steady_error",0));cross=int(m.get("target_crossings",0))
        if rise is not None and rise>1.0 and ov<8:suggestions.append("响应偏慢且超调不大：可以小幅增加 Kp（例如 +5%~10%）后复测。")
        if ov>15 or cross>=3:suggestions.append("超调/反复过零较明显：优先降低 Kp；若已有 D 项，可小幅增加 Kd 并注意噪声。")
        if steady>max(abs(float(m.get("target",0)))*0.03,5):suggestions.append("稳态误差较大：在输出未饱和的前提下，小幅增加 Ki，并注意积分饱和。")
        if not suggestions:suggestions.append("当前响应没有明显单一问题。建议保存本次结果，再用小步长改一个参数后进行 A/B 对比。")
        lines=["阶跃分析完成",f"Score: {score:.2f}",f"Rise: {m.get('rise_time_s')} s",f"Overshoot: {ov:.2f}%",f"Settling: {m.get('settling_time_s')} s",f"Steady error: {steady:.2f}",f"RMSE: {float(m.get('rmse',0)):.2f}","","本地调参建议："]+["• "+x for x in suggestions]
        self.out.setPlainText("\n".join(lines))
        self.store.add("speed_step","速度环阶跃",self.config.get("vehicle",{}).get("display_name",""),parameters=p,metrics={**m,"score":score},samples=sm)
