from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QSpinBox, QMessageBox, QFrame, QTreeWidget,
    QTreeWidgetItem, QStackedWidget, QSplitter
)
from core.config import list_vehicle_files, load_vehicle_config, validate_vehicle_config
from ui.overview import OverviewPage
from ui.scope import ScopePage
from ui.speed_lab import SpeedLab
from ui.heading_lab import HeadingLab
from ui.custom_loop import CustomLoopLab
from ui.ble_dialog import BleConnectDialog
from ui.power_monitor import PowerMonitor
from ui.motor_lab import MotorLab
from ui.parameters import ParametersPage
from ui.track_lab import TrackLab
from ui.profile_manager import ProfileManager
from ui.protocol_monitor import ProtocolMonitor
from ui.msp_assistant import MspAssistant
from ui.ai_tuner import AITunerPage
from ui.chassis_debug import ChassisDebugPage
from ui.chassis_motion import ChassisMotionPage
from ui.experiment_history import ExperimentHistoryPage
from ui.diagnostics import DiagnosticsPage
from ui.theme import THEME_STYLES, apply_plot_theme, make_ikun_icon



PAGE_DEFS = [
    ("实时调试", [
        ("总览", "车辆关键状态", OverviewPage),
        ("示波器", "多通道实时曲线与 A/B 游标", ScopePage),
        ("Speed Lab", "速度环在线调参", SpeedLab),
        ("Heading Lab", "航向外环 + 角速度内环", HeadingLab),
        ("自定义环", "任意 PID 环字段映射", CustomLoopLab),
    ]),
    ("车辆实验", [
        ("AI 调参", "本地规则分析与阶跃测试", AITunerPage),
        ("电源监控", "ADC、电池电压与电流", PowerMonitor),
        ("单电机实验", "单轮 PWM / RPM / 编码器", MotorLab),
        ("底盘调试", "多电机与 IMU 检查", ChassisDebugPage),
        ("麦轮运动", "全向底盘 Vx/Vy/Wz 目标 vs 实际 + PID", ChassisMotionPage),
    ]),
    ("参数与赛道", [
        ("全部参数", "统一读写 MCU 参数", ParametersPage),
        ("参数方案", "保存与恢复整车参数", ProfileManager),
        ("赛道工程", "圈速、入弯/出弯与弯道事件分析", TrackLab),
        ("实验档案", "历史实验与曲线比较", ExperimentHistoryPage),
    ]),
    ("工具", [
        ("系统诊断", "通信和车辆状态诊断", DiagnosticsPage),
        ("协议监视器", "查看 TX / RX 原始报文", ProtocolMonitor),
        ("MSP 适配", "MSPM0 / MSP430 接入帮助", MspAssistant),
    ]),
]


class MainWindow(QMainWindow):
    def __init__(self, bus, transport, config):
        super().__init__()
        self.bus = bus; self.transport = transport; self.config = config
        self.page_specs = []
        self.settings = QSettings("IKUN", "CAR LAB")
        self.theme_name = self.settings.value("theme", "白色")
        if self.theme_name not in THEME_STYLES:
            self.theme_name = "白色"
        self.setWindowTitle("IKUN · CAR LAB v1.6.1")
        self.setMinimumSize(1180, 760)
        self.resize(1500, 900)
        self.setStyleSheet(THEME_STYLES[self.theme_name])
        self.setWindowIcon(make_ikun_icon(self.theme_name))
        self._build()
        self._apply_theme(self.theme_name, persist=False)
        self.bus.connection.connect(self._on_connection)
        self.bus.event.connect(self._on_event)

    def _build(self):
        central = QWidget(); root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10); root.setSpacing(8)
        root.addWidget(self._build_header())

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(self._build_sidebar())
        self.content_wrap = QFrame(); self.content_wrap.setObjectName("panel")
        cl = QVBoxLayout(self.content_wrap); cl.setContentsMargins(10, 8, 10, 10); cl.setSpacing(7)
        title_row = QHBoxLayout()
        self.page_title = QLabel("总览"); self.page_title.setObjectName("pageTitle")
        self.page_desc = QLabel("车辆关键状态"); self.page_desc.setObjectName("muted")
        title_row.addWidget(self.page_title); title_row.addSpacing(8); title_row.addWidget(self.page_desc); title_row.addStretch(1)
        cl.addLayout(title_row)
        self.stack = QStackedWidget(); cl.addWidget(self.stack, 1)
        split.addWidget(self.content_wrap); split.setSizes([220, 1250]); split.setStretchFactor(1, 1)
        root.addWidget(split, 1)
        self.setCentralWidget(central)
        self._rebuild_pages()
        self._select_page(0)

    def _build_header(self):
        top = QFrame(); top.setObjectName("header")
        outer = QVBoxLayout(top); outer.setContentsMargins(13, 10, 13, 10); outer.setSpacing(8)
        row1 = QHBoxLayout()
        brand = QVBoxLayout(); brand.setSpacing(0)
        title = QLabel("IKUN"); title.setObjectName("brandIKUN")
        sub = QLabel("CAR LAB · v1.6.1 · Unified Vehicle Tuning Workbench"); sub.setObjectName("subtitle")
        brand.addWidget(title); brand.addWidget(sub)
        row1.addLayout(brand); row1.addStretch(1)
        row1.addWidget(QLabel("主题"))
        self.theme_combo = QComboBox(); self.theme_combo.addItems(["黑色", "白色"]); self.theme_combo.setFixedWidth(82)
        self.theme_combo.blockSignals(True); self.theme_combo.setCurrentText(self.theme_name); self.theme_combo.blockSignals(False)
        self.theme_combo.currentTextChanged.connect(self._apply_theme)
        row1.addWidget(self.theme_combo)
        self.status = QLabel("未连接"); self.status.setObjectName("statusBad"); row1.addWidget(self.status)
        quick = QLabel("调车工作区")
        quick.setObjectName("muted")
        row1.addWidget(quick)
        for text, idx in [("速度", 2), ("航向", 3), ("示波器", 1), ("弯道", 12)]:
            b=QPushButton(text); b.setFixedHeight(28)
            b.clicked.connect(lambda _=False,i=idx:self._select_page(i))
            row1.addWidget(b)
        self.param_check = QLabel("参数检查：OK"); self.param_check.setObjectName("muted"); row1.addWidget(self.param_check)
        outer.addLayout(row1)

        row = QHBoxLayout(); row.setSpacing(7)
        row.addWidget(QLabel("车型"))
        self.vehicle_combo = QComboBox(); self.vehicle_combo.setMinimumWidth(250)
        self.vehicle_files = list_vehicle_files()
        initial_path = str(self.config.get("_path", ""))
        initial_index = 0
        for i, p in enumerate(self.vehicle_files):
            try:
                c = load_vehicle_config(p); name = c.get("vehicle", {}).get("display_name", p.stem)
            except Exception:
                name = p.stem
            self.vehicle_combo.addItem(name, str(p))
            if str(p) == initial_path: initial_index = i
        self.vehicle_combo.setCurrentIndex(initial_index)
        self.vehicle_combo.currentIndexChanged.connect(self._vehicle_changed)
        row.addWidget(self.vehicle_combo)

        row.addSpacing(8); row.addWidget(QLabel("连接方式"))
        self.mode = QComboBox(); self.mode.addItems(["仿真", "串口", "蓝牙串口", "BLE", "TCP"]); self.mode.setFixedWidth(115)
        row.addWidget(self.mode)
        self.port = QLineEdit("COM3"); self.port.setPlaceholderText("COM3"); self.port.setFixedWidth(78); row.addWidget(self.port)
        self.baud = QComboBox(); self.baud.addItems(["115200", "230400", "460800", "921600"]); self.baud.setFixedWidth(100); row.addWidget(self.baud)
        self.host = QLineEdit("127.0.0.1"); self.host.setFixedWidth(105); row.addWidget(self.host)
        self.tcp_port = QSpinBox(); self.tcp_port.setRange(1,65535); self.tcp_port.setValue(9000); self.tcp_port.setFixedWidth(78); row.addWidget(self.tcp_port)
        self.mode.currentTextChanged.connect(self._update_connection_fields)

        self.connect_btn = QPushButton("连接"); self.connect_btn.setObjectName("primary"); self.connect_btn.clicked.connect(self._connect); row.addWidget(self.connect_btn)
        self.disconnect_btn = QPushButton("断开"); self.disconnect_btn.clicked.connect(self.transport.disconnect); row.addWidget(self.disconnect_btn)
        self.estop = QPushButton("急停"); self.estop.setObjectName("danger"); self.estop.clicked.connect(lambda:self.transport.command("emergency_stop", True)); row.addWidget(self.estop)
        row.addStretch(1)
        self.vehicle_hint = QLabel(""); self.vehicle_hint.setObjectName("muted"); row.addWidget(self.vehicle_hint)
        outer.addLayout(row)
        self._apply_vehicle_defaults(self.config)
        self._update_parameter_check(self.config)
        self._update_connection_fields(self.mode.currentText())
        return top

    def _build_sidebar(self):
        side = QFrame(); side.setObjectName("sidebar"); side.setMinimumWidth(205); side.setMaximumWidth(270)
        lay = QVBoxLayout(side); lay.setContentsMargins(6, 8, 6, 8)
        self.nav = QTreeWidget()
        self.nav.setHeaderHidden(True)
        self.nav.setIndentation(16)
        self.nav.setRootIsDecorated(True)
        self.nav.setItemsExpandable(True)
        self.nav.setExpandsOnDoubleClick(False)

        page_index = 0
        for group_name, pages in PAGE_DEFS:
            # 真正的分组节点：点击标题可展开/收起，页面作为其子节点。
            group = QTreeWidgetItem([group_name])
            group.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            group.setData(0, Qt.ItemDataRole.UserRole + 1, "group")
            self.nav.addTopLevelItem(group)

            font = group.font(0)
            font.setBold(True)
            group.setFont(0, font)

            for name, desc, cls in pages:
                item = QTreeWidgetItem([name])
                item.setData(0, Qt.ItemDataRole.UserRole, page_index)
                item.setData(0, Qt.ItemDataRole.UserRole + 1, "page")
                item.setToolTip(0, desc)
                group.addChild(item)
                self.page_specs.append((name, desc, cls))
                page_index += 1

            group.setExpanded(True)

        self.nav.currentItemChanged.connect(self._nav_changed)
        self.nav.itemClicked.connect(self._nav_clicked)
        lay.addWidget(self.nav, 1)
        foot = QLabel("点击分类可展开/收起；点击具体功能进入页面。车型切换会重新加载字段映射。")
        foot.setObjectName("muted"); foot.setWordWrap(True); lay.addWidget(foot)
        return side

    def _instantiate_page(self, cls):
        if cls in (OverviewPage, ScopePage, PowerMonitor, TrackLab, MspAssistant):
            if cls is MspAssistant: return cls(self.config)
            return cls(self.bus, self.config)
        if cls is ProtocolMonitor:
            return cls(self.bus, self.transport)
        return cls(self.bus, self.transport, self.config)

    def _rebuild_pages(self):
        while self.stack.count():
            w = self.stack.widget(0); self.stack.removeWidget(w); w.deleteLater()
        for _, _, cls in self.page_specs:
            self.stack.addWidget(self._instantiate_page(cls))

    def _nav_clicked(self, item, column):
        if item is None:
            return
        kind = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if kind == "group":
            item.setExpanded(not item.isExpanded())

    def _nav_changed(self, current, previous):
        if current is None:
            return
        idx = current.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(idx, int):
            self._select_page(idx)

    def _find_nav_page_item(self, idx):
        for i in range(self.nav.topLevelItemCount()):
            group = self.nav.topLevelItem(i)
            for j in range(group.childCount()):
                item = group.child(j)
                if item.data(0, Qt.ItemDataRole.UserRole) == idx:
                    return item
        return None

    def _select_page(self, idx):
        if idx < 0 or idx >= len(self.page_specs):
            return
        self.stack.setCurrentIndex(idx)
        name, desc, _ = self.page_specs[idx]
        self.page_title.setText(name)
        self.page_desc.setText(desc)
        item = self._find_nav_page_item(idx)
        if item is not None:
            parent = item.parent()
            if parent is not None:
                parent.setExpanded(True)
            if self.nav.currentItem() is not item:
                self.nav.setCurrentItem(item)


    def _apply_theme(self, theme_name, persist=True):
        if theme_name not in THEME_STYLES:
            theme_name = "黑色"
        self.theme_name = theme_name
        self.setStyleSheet(THEME_STYLES[theme_name])
        self.setWindowIcon(make_ikun_icon(theme_name))
        apply_plot_theme(self, theme_name)
        if hasattr(self, "theme_combo") and self.theme_combo.currentText() != theme_name:
            self.theme_combo.blockSignals(True)
            self.theme_combo.setCurrentText(theme_name)
            self.theme_combo.blockSignals(False)
        if persist:
            self.settings.setValue("theme", theme_name)

    def _vehicle_changed(self, index):
        path = self.vehicle_combo.currentData()
        if not path: return
        try:
            cfg = load_vehicle_config(path)
        except Exception as e:
            QMessageBox.warning(self, "车型配置读取失败", str(e)); return
        if self.transport.connected:
            self.transport.disconnect()
        self.config = cfg; self.transport.config = cfg
        self._apply_vehicle_defaults(cfg)
        self._update_parameter_check(cfg)
        current = self.stack.currentIndex() if hasattr(self, "stack") else 0
        if hasattr(self, "stack"):
            self._rebuild_pages(); self._select_page(max(0,current))
            self._apply_theme(self.theme_name, persist=False)
        self.vehicle_hint.setText(cfg.get("vehicle",{}).get("type", ""))

    def _apply_vehicle_defaults(self, cfg):
        t = cfg.get("transport", {})
        typ = str(t.get("type", "serial")).lower()
        mode_map = {"sim":"仿真", "serial":"串口", "bluetooth_serial":"蓝牙串口", "ble":"BLE", "tcp":"TCP"}
        if hasattr(self, "mode"): self.mode.setCurrentText(mode_map.get(typ, "串口"))
        if hasattr(self, "port"): self.port.setText(str(t.get("port", "COM3")))
        if hasattr(self, "baud"):
            baud = str(t.get("baudrate", 115200))
            if self.baud.findText(baud) < 0: self.baud.addItem(baud)
            self.baud.setCurrentText(baud)
        if hasattr(self, "host"): self.host.setText(str(t.get("host", "127.0.0.1")))
        if hasattr(self, "tcp_port"): self.tcp_port.setValue(int(t.get("tcp_port", t.get("port_number", 9000))))

    def _update_parameter_check(self, cfg):
        issues=validate_vehicle_config(cfg)
        errors=[x for x in issues if x.get("severity")=="error"]
        if errors:
            self.param_check.setText(f"参数检查：{len(errors)} 个错误")
            self.param_check.setToolTip("\n".join(x["message"] for x in errors))
            self.param_check.setStyleSheet("color:#b42318;font-weight:700;")
        elif issues:
            self.param_check.setText(f"参数检查：{len(issues)} 条提示")
            self.param_check.setToolTip("\n".join(x["message"] for x in issues))
            self.param_check.setStyleSheet("color:#9a6700;font-weight:700;")
        else:
            self.param_check.setText("参数检查：OK")
            self.param_check.setToolTip("未发现明显 key 冲突。")
            self.param_check.setStyleSheet("color:#1a7f37;font-weight:700;")

    def _update_connection_fields(self, mode):
        serial = mode in ("串口", "蓝牙串口")
        tcp = mode == "TCP"
        self.port.setVisible(serial); self.baud.setVisible(serial)
        self.host.setVisible(tcp); self.tcp_port.setVisible(tcp)

    def _connect(self):
        try:
            mode = self.mode.currentText()
            if mode == "仿真": self.transport.connect_sim()
            elif mode == "串口": self.transport.connect_serial(self.port.text().strip(), int(self.baud.currentText()), label="串口")
            elif mode == "蓝牙串口": self.transport.connect_serial(self.port.text().strip(), int(self.baud.currentText()), label="蓝牙串口")
            elif mode == "BLE":
                dlg = BleConnectDialog(self.transport, self.config.get("ble", {}), self)
                if not dlg.exec(): return
                v = dlg.values(); self.transport.connect_ble(v["address"], v["write_uuid"], v["notify_uuid"], v["auto_reconnect"])
            else: self.transport.connect_tcp(self.host.text().strip(), self.tcp_port.value())
        except Exception as e:
            QMessageBox.critical(self, "连接失败", str(e))

    def _on_connection(self, ok, text):
        self.status.setText(text); self.status.setObjectName("statusGood" if ok else "statusBad")
        self.status.style().unpolish(self.status); self.status.style().polish(self.status)
        self.connect_btn.setText("已连接" if ok else "连接")

    def _on_event(self, typ, data):
        if typ == "transport_error":
            self.status.setText("通信错误: " + str(data.get("message", ""))); self.status.setObjectName("statusBad")
            self.status.style().unpolish(self.status); self.status.style().polish(self.status)
