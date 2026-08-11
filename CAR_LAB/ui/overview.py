from PySide6.QtWidgets import QWidget, QGridLayout, QVBoxLayout, QLabel, QFrame


class ValueCard(QFrame):
    def __init__(self, title, unit=""):
        super().__init__(); self.setObjectName("card")
        lay = QVBoxLayout(self)
        t = QLabel(title); t.setStyleSheet("color:#9fb0c3")
        self.val = QLabel("--")
        self.val.setStyleSheet("font-size:30px;font-weight:700")
        self.unit = unit
        lay.addWidget(t); lay.addWidget(self.val)
    def set_value(self, value):
        try: self.val.setText(f"{float(value):.2f} {self.unit}")
        except Exception: self.val.setText(str(value))


class OverviewPage(QWidget):
    def __init__(self, bus, config):
        super().__init__()
        grid = QGridLayout(self)
        self.cards = {
            "speed": ValueCard("车速", "m/s"),
            "actual_rpm": ValueCard("实际 RPM", "rpm"),
            "yaw": ValueCard("航向角", "°"),
            "gyro_z": ValueCard("角速度", "°/s"),
            "battery": ValueCard("电池电压", "V"),
            "steering_output": ValueCard("转向输出", "%"),
        }
        for i, c in enumerate(self.cards.values()): grid.addWidget(c, i//3, i%3)
        bus.telemetry.connect(self._tel)
    def _tel(self, d):
        for k, c in self.cards.items():
            if k in d: c.set_value(d[k])
