from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QTableWidget,QTableWidgetItem,QPushButton

class ParametersPage(QWidget):
    def __init__(self,bus,transport,config):
        super().__init__()
        self.bus=bus; self.transport=transport; self.params=config.get("parameters",[]) or []
        root=QVBoxLayout(self)
        self.table=QTableWidget(len(self.params),4)
        self.table.setHorizontalHeaderLabels(["名称","key","当前/输入值","同步状态"])
        for r,p in enumerate(self.params):
            self.table.setItem(r,0,QTableWidgetItem(str(p.get("label",p.get("key","")))))
            self.table.setItem(r,1,QTableWidgetItem(str(p.get("key",""))))
            self.table.setItem(r,2,QTableWidgetItem(str(p.get("default",0))))
            self.table.setItem(r,3,QTableWidgetItem("待命"))
        root.addWidget(self.table)
        row=QHBoxLayout(); read=QPushButton("读取全部"); send=QPushButton("下发选中行")
        read.clicked.connect(self._read_all); send.clicked.connect(self._send_selected)
        row.addWidget(read); row.addWidget(send); row.addStretch(); root.addLayout(row)
        bus.ack.connect(self._ack_legacy); bus.parameter_sync.connect(self._sync)

    def _read_all(self):
        for p in self.params: self.transport.get_param(p.get("key",""))

    def _send_selected(self):
        r=self.table.currentRow()
        if r<0:return
        key=self.table.item(r,1).text()
        try: val=float(self.table.item(r,2).text())
        except ValueError:
            self.table.item(r,3).setText("输入值非法"); return
        self.transport.set_param(key,val)
        self.table.item(r,3).setText("缓冲中")

    def _ack_legacy(self,key,value):
        for r in range(self.table.rowCount()):
            if self.table.item(r,1).text()==key and value is not None:
                self.table.item(r,2).setText(str(value))

    def _sync(self,info):
        key=str(info.get("key",""))
        mapping={
            "queued":"缓冲中","sending":"发送中","timeout":"ACK超时·重试",
            "retry":"重试中","mismatch":"回读不一致","acked":"已确认 ✓","deferred":"暂存·待重试"
        }
        for r in range(self.table.rowCount()):
            if self.table.item(r,1).text()==key:
                self.table.item(r,3).setText(mapping.get(info.get("state",""), str(info.get("state",""))))
                if info.get("state")=="acked" and info.get("value") is not None:
                    self.table.item(r,2).setText(str(info.get("value")))
                break
