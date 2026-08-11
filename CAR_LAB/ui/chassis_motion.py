"""麦轮 / 全向底盘运动解算调试页。

按车型 ``config.chassis_motion.axes`` 渲染底盘速度环：
目标 vs 实际 Vx / Vy / Wz，一键发送目标、在线 SET 三个 PID，并画目标/实际曲线。
非麦轮车型（配置里没有 chassis_motion）显示提示。
"""
from __future__ import annotations
import time
from collections import deque
import pyqtgraph as pg
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QPushButton, QDoubleSpinBox, QComboBox,
)

_PALETTE = [(45, 108, 210), (220, 135, 40), (190, 65, 75)]


class ChassisMotionPage(QWidget):
    def __init__(self, bus, transport, config):
        super().__init__()
        self.bus = bus
        self.transport = transport
        self.motion = config.get("chassis_motion", {}) or {}
        self.axes = list(self.motion.get("axes", []) or [])
        self.t0 = time.monotonic()
        self.t = deque(maxlen=3000)
        self.series = {}   # axis_key -> {"target": deque, "actual": deque}
        self.readouts = {}  # axis_key -> (target_label, actual_label)
        self.targets = {}   # axis_key -> QDoubleSpinBox
        self.pid_spins = {}  # axis_key -> {"Kp":spin,...}
        self.curves = {}    # axis_key -> {"target":curve,"actual":curve}

        root = QVBoxLayout(self)
        if not self.axes:
            hint = QLabel(
                "当前车型未启用底盘运动解算。\n\n"
                "只有麦克纳姆轮 / 全向轮等车型需要 Vx / Vy / Wz 解算层；\n"
                "在车型 YAML 中添加 chassis_motion.axes 即可在此调底盘 PID。"
            )
            hint.setObjectName("muted")
            root.addWidget(hint)
            root.addStretch(1)
            return

        if self.motion.get("hint"):
            tip = QLabel(str(self.motion["hint"]))
            tip.setObjectName("muted")
            tip.setWordWrap(True)
            root.addWidget(tip)

        body = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(8)
        right = QVBoxLayout()
        right.setSpacing(8)

        for idx, axis in enumerate(self.axes):
            key = str(axis.get("key", f"axis{idx}"))
            label = str(axis.get("label", key))
            unit = str(axis.get("unit", ""))
            self.series[key] = {"target": deque(maxlen=3000), "actual": deque(maxlen=3000)}

            box = QGroupBox(label)
            g = QGridLayout(box)
            # 目标 / 实际 数值读出
            tl = QLabel("目标 --"); al = QLabel("实际 --")
            tl.setStyleSheet("font-weight:700")
            g.addWidget(tl, 0, 0); g.addWidget(al, 0, 1, 1, 2)
            self.readouts[key] = (tl, al, unit)
            # 目标发送
            sp = QDoubleSpinBox(); sp.setRange(-1e6, 1e6); sp.setDecimals(4); sp.setSingleStep(0.05)
            send = QPushButton("发送目标")
            send.clicked.connect(lambda _=False, a=axis, s=sp: self._send_target(a, s.value()))
            g.addWidget(QLabel(f"目标 {unit}"), 1, 0); g.addWidget(sp, 1, 1); g.addWidget(send, 1, 2)
            self.targets[key] = sp
            # 在线 PID
            spins = {}
            params = axis.get("params", {}) or {}
            for c, name in enumerate(("Kp", "Ki", "Kd")):
                s = QDoubleSpinBox(); s.setRange(-99999, 99999); s.setDecimals(6); s.setSingleStep(0.01)
                pkey = str(params.get(name, "")).strip()
                if pkey:
                    s.valueChanged.connect(lambda v, k=pkey: self.transport.set_param(k, v))
                    s.setToolTip(f"SET {pkey}")
                else:
                    s.setEnabled(False)
                g.addWidget(QLabel(name), 2, c)
                g.addWidget(s, 3, c)
                spins[name] = s
            self.pid_spins[key] = spins
            left.addWidget(box)

            plot = pg.PlotWidget(title=f"{label}：目标 / 实际")
            plot.showGrid(x=True, y=True, alpha=.18)
            plot.addLegend()
            color = _PALETTE[idx % len(_PALETTE)]
            ct = plot.plot(name="目标", pen=pg.mkPen(color, width=2, style=pg.QtCore.Qt.PenStyle.DashLine))
            ca = plot.plot(name="实际", pen=pg.mkPen(color, width=2))
            self.curves[key] = {"target": ct, "actual": ca}
            right.addWidget(plot, 1)

        left.addStretch(1)
        stop = QPushButton("底盘急停")
        stop.setObjectName("danger")
        stop.clicked.connect(lambda: self.transport.command("emergency_stop", True))
        left.addWidget(stop)

        body.addLayout(left, 0)
        body.addLayout(right, 1)
        root.addLayout(body, 1)

        bus.telemetry.connect(self._tel)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._draw)
        self.timer.start(50)

    def _send_target(self, axis, value):
        key = str(axis.get("command_key", "")).strip()
        if key:
            self.transport.command(key, value)

    def _tel(self, d):
        if not self.axes:
            return
        self.t.append(time.monotonic() - self.t0)
        for axis in self.axes:
            key = str(axis.get("key"))

            def val(field):
                k = str(axis.get(field, "")).strip()
                try:
                    return float(d.get(k)) if k in d else None
                except Exception:
                    return None

            tv = val("target_key"); av = val("actual_key")
            s = self.series[key]
            s["target"].append(tv if tv is not None else (s["target"][-1] if s["target"] else 0.0))
            s["actual"].append(av if av is not None else (s["actual"][-1] if s["actual"] else 0.0))
            tl, al, unit = self.readouts[key]
            if tv is not None:
                tl.setText(f"目标 {tv:+.3f} {unit}")
            if av is not None:
                al.setText(f"实际 {av:+.3f} {unit}")

    def _draw(self):
        x = list(self.t)
        if not x:
            return
        for key, c in self.curves.items():
            for field in ("target", "actual"):
                y = list(self.series[key][field])
                n = min(len(x), len(y))
                c[field].setData(x[-n:], y[-n:])
