from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox, QLineEdit,
    QPushButton, QCheckBox, QLabel, QMessageBox, QDialogButtonBox
)


class BleConnectDialog(QDialog):
    def __init__(self, transport, defaults=None, parent=None):
        super().__init__(parent)
        self.transport = transport
        self.defaults = defaults or {}
        self.setWindowTitle("BLE 连接")
        self.resize(650, 280)
        root = QVBoxLayout(self)
        root.addWidget(QLabel("BLE 使用 GATT Notify 接收、Write 发送。MCU/蓝牙模块需提供对应特征 UUID。"))
        form = QFormLayout()
        row = QHBoxLayout()
        self.device = QComboBox(); self.device.setEditable(True)
        default_address = str(self.defaults.get("address", "")).strip()
        if default_address:
            self.device.addItem(default_address, default_address)
        self.scan_btn = QPushButton("扫描 BLE")
        self.scan_btn.clicked.connect(self._scan)
        row.addWidget(self.device, 1); row.addWidget(self.scan_btn)
        form.addRow("设备 / 地址", row)
        self.write_uuid = QLineEdit(str(self.defaults.get("write_uuid", "")))
        self.notify_uuid = QLineEdit(str(self.defaults.get("notify_uuid", "")))
        form.addRow("Write UUID (PC→MCU)", self.write_uuid)
        form.addRow("Notify UUID (MCU→PC)", self.notify_uuid)
        self.reconnect = QCheckBox("断线后自动重连"); self.reconnect.setChecked(True)
        form.addRow("", self.reconnect)
        root.addLayout(form)
        note = QLabel("蓝牙串口模块（如 HC-05）不需要 BLE UUID：主界面直接选“蓝牙串口”，填写 Windows 分配的 COM 口即可。")
        note.setWordWrap(True); root.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def _scan(self):
        self.scan_btn.setEnabled(False); self.scan_btn.setText("扫描中…")
        try:
            devices = self.transport.scan_ble(4.0)
            self.device.clear()
            for name, address in devices:
                self.device.addItem(f"{name}  [{address}]", address)
            if not devices:
                QMessageBox.information(self, "BLE", "没有发现 BLE 设备。请确认设备正在广播。")
        except Exception as exc:
            QMessageBox.critical(self, "BLE 扫描失败", str(exc))
        finally:
            self.scan_btn.setEnabled(True); self.scan_btn.setText("扫描 BLE")

    def values(self):
        address = self.device.currentData()
        if not address:
            text = self.device.currentText().strip()
            if "[" in text and text.endswith("]"):
                address = text.rsplit("[", 1)[1][:-1]
            else:
                address = text
        return {
            "address": str(address or "").strip(),
            "write_uuid": self.write_uuid.text().strip(),
            "notify_uuid": self.notify_uuid.text().strip(),
            "auto_reconnect": self.reconnect.isChecked(),
        }
