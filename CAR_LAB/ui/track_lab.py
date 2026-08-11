import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QLineEdit, QGroupBox, QDoubleSpinBox, QSpinBox,
    QComboBox, QFrame, QSplitter, QHeaderView
)

from core.corner_analyzer import CornerAnalyzer


class TrackLab(QWidget):
    def __init__(self, bus, config):
        super().__init__()
        self.cfg = config.get("track_analysis", {})
        self.running = False
        self.lap_start = None
        self.session_start = None
        self.samples = []
        self.laps = []
        self.last_trigger = 0
        self.lap_enter_base = 0
        self.lap_exit_base = 0

        corner_cfg = dict(self.cfg.get("corner_analysis", {}) or {})
        corner_cfg.setdefault("speed_key", self.cfg.get("speed_key", "speed"))
        corner_cfg.setdefault("error_key", self.cfg.get("error_key", "tracking_error"))
        corner_cfg.setdefault("yaw_rate_key", self.cfg.get("yaw_rate_key", "gyro_z"))
        corner_cfg.setdefault("curvature_key", self.cfg.get("curvature_key", "curvature"))
        self.corner = CornerAnalyzer(corner_cfg)

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(8)

        root.addWidget(self._build_session_bar())
        root.addWidget(self._build_corner_settings())
        root.addLayout(self._build_count_cards())

        self.status = QLabel("未开始 · 入弯/出弯识别将在跑圈开始后工作")
        self.status.setObjectName("muted")
        root.addWidget(self.status)

        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self._build_lap_panel())
        split.addWidget(self._build_corner_panel())
        split.setSizes([270, 430])
        split.setStretchFactor(1, 1)
        root.addWidget(split, 1)

        bus.telemetry.connect(self._tel)
        self._sync_corner_controls_from_config()
        self._refresh_counts()

    def _build_session_bar(self):
        box = QFrame()
        box.setObjectName("toolbar")
        row = QHBoxLayout(box)
        row.setContentsMargins(10, 8, 10, 8)
        row.addWidget(QLabel("赛道"))
        self.track = QLineEdit("测试赛道")
        self.track.setMinimumWidth(180)
        row.addWidget(self.track)
        self.start_btn = QPushButton("开始跑圈")
        self.start_btn.setObjectName("primary")
        self.lap_btn = QPushButton("手动完成一圈")
        self.stop_btn = QPushButton("停止")
        self.start_btn.clicked.connect(self._start)
        self.lap_btn.clicked.connect(self._finish_lap)
        self.stop_btn.clicked.connect(self._stop)
        row.addWidget(self.start_btn)
        row.addWidget(self.lap_btn)
        row.addWidget(self.stop_btn)
        row.addStretch(1)
        hint = QLabel("自动计圈：MCU 的 lap_trigger 产生 0→1 脉冲")
        hint.setObjectName("muted")
        row.addWidget(hint)
        return box

    def _build_corner_settings(self):
        group = QGroupBox("弯道识别 · 滞回 + 持续时间确认，避免抖动重复计数")
        row = QHBoxLayout(group)
        row.addWidget(QLabel("检测源"))
        self.source_combo = QComboBox()
        self.source_combo.addItem("角速度 gyro_z", "yaw_rate")
        self.source_combo.addItem("赛道曲率 curvature", "curvature")
        self.source_combo.addItem("自动", "auto")
        self.source_combo.currentIndexChanged.connect(self._source_changed)
        row.addWidget(self.source_combo)

        self.threshold_label = QLabel("阈值")
        row.addWidget(self.threshold_label)
        self.enter_threshold = QDoubleSpinBox()
        self.enter_threshold.setRange(0.0001, 1000.0)
        self.enter_threshold.setDecimals(4)
        self.enter_threshold.setSingleStep(1.0)
        self.exit_threshold = QDoubleSpinBox()
        self.exit_threshold.setRange(0.0, 1000.0)
        self.exit_threshold.setDecimals(4)
        self.exit_threshold.setSingleStep(1.0)
        row.addWidget(QLabel("入弯"))
        row.addWidget(self.enter_threshold)
        row.addWidget(QLabel("出弯"))
        row.addWidget(self.exit_threshold)

        row.addWidget(QLabel("入弯确认"))
        self.enter_hold = QSpinBox()
        self.enter_hold.setRange(0, 2000)
        self.enter_hold.setSuffix(" ms")
        row.addWidget(self.enter_hold)
        row.addWidget(QLabel("出弯确认"))
        self.exit_hold = QSpinBox()
        self.exit_hold.setRange(0, 3000)
        self.exit_hold.setSuffix(" ms")
        row.addWidget(self.exit_hold)

        self.apply_corner_btn = QPushButton("应用识别参数")
        self.apply_corner_btn.clicked.connect(self._apply_corner_settings)
        row.addWidget(self.apply_corner_btn)
        row.addStretch(1)
        return group

    def _count_card(self, title):
        frame = QFrame()
        frame.setObjectName("card")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(12, 7, 12, 7)
        title_label = QLabel(title)
        title_label.setObjectName("muted")
        value = QLabel("0")
        value.setStyleSheet("font-size:22px;font-weight:800;")
        lay.addWidget(title_label)
        lay.addWidget(value)
        return frame, value

    def _build_count_cards(self):
        row = QHBoxLayout()
        c, self.enter_count_label = self._count_card("入弯次数")
        row.addWidget(c)
        c, self.exit_count_label = self._count_card("出弯次数")
        row.addWidget(c)
        c, self.left_count_label = self._count_card("左弯")
        row.addWidget(c)
        c, self.right_count_label = self._count_card("右弯")
        row.addWidget(c)
        c, self.current_corner_label = self._count_card("当前状态")
        self.current_corner_label.setText("直线")
        self.current_corner_label.setStyleSheet("font-size:18px;font-weight:800;")
        row.addWidget(c)
        row.addStretch(1)
        return row

    def _build_lap_panel(self):
        box = QFrame()
        box.setObjectName("panel")
        lay = QVBoxLayout(box)
        title = QLabel("圈速摘要")
        title.setObjectName("panelTitle")
        lay.addWidget(title)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "圈", "圈速(s)", "平均速度", "最高速度", "平均循迹误差", "最低电压", "入弯", "出弯"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.table, 1)
        return box

    def _build_corner_panel(self):
        box = QFrame()
        box.setObjectName("panel")
        lay = QVBoxLayout(box)
        row = QHBoxLayout()
        title = QLabel("Corner Analyzer · 每个弯道事件")
        title.setObjectName("panelTitle")
        row.addWidget(title)
        row.addStretch(1)
        note = QLabel("S 弯方向反转也会分成两个弯道事件")
        note.setObjectName("muted")
        row.addWidget(note)
        lay.addLayout(row)

        self.corner_table = QTableWidget(0, 11)
        self.corner_table.setHorizontalHeaderLabels([
            "#", "圈", "方向", "入弯t(s)", "出弯t(s)", "入弯速度", "最低速度",
            "出弯速度", "弯道耗时(s)", "最大循迹误差", "峰值角速度"
        ])
        self.corner_table.setAlternatingRowColors(True)
        self.corner_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.corner_table, 1)
        return box

    def _sync_corner_controls_from_config(self):
        src = self.corner.source
        idx = self.source_combo.findData(src)
        if idx < 0:
            idx = self.source_combo.findData("yaw_rate")
        self.source_combo.blockSignals(True)
        self.source_combo.setCurrentIndex(max(0, idx))
        self.source_combo.blockSignals(False)
        self.enter_hold.setValue(int(round(self.corner.enter_hold_s * 1000)))
        self.exit_hold.setValue(int(round(self.corner.exit_hold_s * 1000)))
        self._source_changed()

    def _source_changed(self):
        source = self.source_combo.currentData() or "yaw_rate"
        if source == "curvature":
            self.threshold_label.setText("阈值 (1/m)")
            self.enter_threshold.setDecimals(4)
            self.exit_threshold.setDecimals(4)
            self.enter_threshold.setSingleStep(0.01)
            self.exit_threshold.setSingleStep(0.01)
            self.enter_threshold.setValue(self.corner.enter_curvature)
            self.exit_threshold.setValue(self.corner.exit_curvature)
        elif source == "auto":
            self.threshold_label.setText("阈值 (自动源)")
            # Auto uses curvature when curvature exists, otherwise yaw rate.
            self.enter_threshold.setDecimals(4)
            self.exit_threshold.setDecimals(4)
            self.enter_threshold.setSingleStep(0.01)
            self.exit_threshold.setSingleStep(0.01)
            self.enter_threshold.setValue(self.corner.enter_curvature)
            self.exit_threshold.setValue(self.corner.exit_curvature)
        else:
            self.threshold_label.setText("阈值 (°/s)")
            self.enter_threshold.setDecimals(1)
            self.exit_threshold.setDecimals(1)
            self.enter_threshold.setSingleStep(1.0)
            self.exit_threshold.setSingleStep(1.0)
            self.enter_threshold.setValue(self.corner.enter_yaw_rate)
            self.exit_threshold.setValue(self.corner.exit_yaw_rate)

    def _settings_from_controls(self):
        cfg = dict(self.corner.cfg)
        source = self.source_combo.currentData() or "yaw_rate"
        cfg["source"] = source
        cfg["enter_hold_ms"] = self.enter_hold.value()
        cfg["exit_hold_ms"] = self.exit_hold.value()
        if source in ("curvature", "auto"):
            cfg["enter_curvature"] = self.enter_threshold.value()
            cfg["exit_curvature"] = self.exit_threshold.value()
        else:
            cfg["enter_yaw_rate"] = self.enter_threshold.value()
            cfg["exit_yaw_rate"] = self.exit_threshold.value()
        return cfg

    def _apply_corner_settings(self):
        if self.running:
            self.status.setText("正在记录：新的弯道识别参数将在下一次“开始跑圈”时生效")
            return
        self.corner.configure(self._settings_from_controls())
        self.corner.reset()
        self._refresh_counts()
        self.status.setText("弯道识别参数已应用")

    def _start(self):
        self.corner.configure(self._settings_from_controls())
        self.corner.reset()
        self.running = True
        self.session_start = time.monotonic()
        self.lap_start = self.session_start
        self.samples = []
        self.laps = []
        self.last_trigger = 0
        self.lap_enter_base = 0
        self.lap_exit_base = 0
        self.table.setRowCount(0)
        self.corner_table.setRowCount(0)
        self._refresh_counts()
        self.status.setText("记录中 · 当前直线")

    def _stop(self):
        self.running = False
        counts = self.corner.counts()
        suffix = " · 当前仍在弯中" if self.corner.active_corner() else ""
        self.status.setText(
            f"已停止，共 {len(self.laps)} 圈，入弯 {counts['enter']} 次，出弯 {counts['exit']} 次{suffix}"
        )

    def _finish_lap(self):
        if not self.running or self.lap_start is None:
            return
        now = time.monotonic()
        lap_time = now - self.lap_start
        self.lap_start = now
        if not self.samples:
            return

        sk = self.cfg.get("speed_key", "speed")
        ek = self.cfg.get("error_key", "tracking_error")
        bk = self.cfg.get("battery_key", "battery")
        speeds = [float(x.get(sk, 0) or 0) for x in self.samples]
        errs = [abs(float(x.get(ek, 0) or 0)) for x in self.samples]
        bats = [float(x.get(bk, 999)) for x in self.samples if bk in x]
        counts = self.corner.counts()
        lap_enter = counts["enter"] - self.lap_enter_base
        lap_exit = counts["exit"] - self.lap_exit_base

        item = (
            lap_time,
            sum(speeds) / len(speeds),
            max(speeds),
            sum(errs) / len(errs),
            min(bats) if bats else 0,
            lap_enter,
            lap_exit,
        )
        self.laps.append(item)
        self.samples = []
        self.lap_enter_base = counts["enter"]
        self.lap_exit_base = counts["exit"]

        r = self.table.rowCount()
        self.table.insertRow(r)
        vals = [r + 1, *item]
        for c, value in enumerate(vals):
            if isinstance(value, float):
                text = f"{value:.3f}"
            else:
                text = str(value)
            self.table.setItem(r, c, QTableWidgetItem(text))
        self.status.setText(
            f"第 {r + 1} 圈：{lap_time:.3f}s · 入弯 {lap_enter} · 出弯 {lap_exit}"
        )

    def _add_corner_row(self, corner):
        r = self.corner_table.rowCount()
        self.corner_table.insertRow(r)
        values = [
            corner.get("index", r + 1),
            corner.get("lap_no", ""),
            corner.get("direction", ""),
            corner.get("enter_time", 0.0),
            corner.get("exit_time", 0.0),
            corner.get("enter_speed", 0.0),
            corner.get("min_speed", 0.0),
            corner.get("exit_speed", 0.0),
            corner.get("duration", 0.0),
            corner.get("max_error", 0.0),
            corner.get("peak_yaw_rate", 0.0),
        ]
        for c, value in enumerate(values):
            if isinstance(value, float):
                text = f"{value:.3f}"
            else:
                text = str(value)
            self.corner_table.setItem(r, c, QTableWidgetItem(text))
        self.corner_table.scrollToBottom()

    def _refresh_counts(self):
        counts = self.corner.counts()
        self.enter_count_label.setText(str(counts["enter"]))
        self.exit_count_label.setText(str(counts["exit"]))
        self.left_count_label.setText(str(counts["left"]))
        self.right_count_label.setText(str(counts["right"]))
        active = self.corner.active_corner()
        if active:
            self.current_corner_label.setText(active.get("direction", "弯中"))
        else:
            self.current_corner_label.setText("直线")

    def _tel(self, data):
        if not self.running:
            return
        now = time.monotonic()
        sample_time = now - self.session_start if self.session_start is not None else 0.0
        self.samples.append(dict(data))
        lap_no = len(self.laps) + 1

        events = self.corner.update(data, sample_time, lap_no=lap_no)
        for event in events:
            typ = event.get("type")
            corner = event.get("corner", {})
            if typ == "enter":
                self.status.setText(
                    f"记录中 · 入弯 #{corner.get('index', '?')} · {corner.get('direction', '')} · "
                    f"入弯速度 {corner.get('enter_speed', 0):.3f}"
                )
            elif typ == "exit":
                self._add_corner_row(corner)
                self.status.setText(
                    f"记录中 · 出弯 #{corner.get('index', '?')} · 耗时 {corner.get('duration', 0):.3f}s · "
                    f"出弯速度 {corner.get('exit_speed', 0):.3f}"
                )
        self._refresh_counts()

        trig_key = self.cfg.get("lap_trigger_key", "lap_trigger")
        trig = int(data.get(trig_key, 0) or 0)
        if trig and not self.last_trigger:
            self._finish_lap()
        self.last_trigger = trig
