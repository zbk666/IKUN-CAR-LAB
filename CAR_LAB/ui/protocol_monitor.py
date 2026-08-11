import json
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QPlainTextEdit,QLineEdit,QPushButton


class ProtocolMonitor(QWidget):
    def __init__(self,bus,transport):
        super().__init__();self.transport=transport;root=QVBoxLayout(self);self.log=QPlainTextEdit();self.log.setReadOnly(True);self.log.setMaximumBlockCount(2000);root.addWidget(self.log,1)
        row=QHBoxLayout();self.input=QLineEdit('{"type":"GET","key":"speed_kp"}');send=QPushButton("发送 JSON");clear=QPushButton("清空");send.clicked.connect(self._send);clear.clicked.connect(self.log.clear);row.addWidget(self.input,1);row.addWidget(send);row.addWidget(clear);root.addLayout(row)
        bus.tx_text.connect(lambda s:self.log.appendPlainText("TX > "+s));bus.rx_text.connect(lambda s:self.log.appendPlainText("RX < "+s))
    def _send(self):
        try:self.transport.send_obj(json.loads(self.input.text()))
        except Exception as e:self.log.appendPlainText("ERR  "+str(e))
