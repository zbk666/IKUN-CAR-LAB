from pathlib import Path
import yaml
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLineEdit,QPushButton,QComboBox,QPlainTextEdit,QMessageBox
ROOT=Path(__file__).resolve().parents[1]

class ProfileManager(QWidget):
    def __init__(self,bus,transport,config):
        super().__init__();self.transport=transport;self.config=config;self.params=config.get("parameters",[]);self.values={};vid=config.get("vehicle",{}).get("id","default");self.dir=ROOT/"profiles"/str(vid);self.dir.mkdir(parents=True,exist_ok=True)
        root=QVBoxLayout(self);row=QHBoxLayout();self.name=QLineEdit("stable");self.combo=QComboBox();read=QPushButton("读取全部参数");save=QPushButton("保存当前方案");load=QPushButton("加载并下发");read.clicked.connect(self._read_all);row.addWidget(self.name);row.addWidget(read);row.addWidget(save);row.addWidget(self.combo);row.addWidget(load);root.addLayout(row)
        self.preview=QPlainTextEdit();self.preview.setReadOnly(True);root.addWidget(self.preview);save.clicked.connect(self._save);load.clicked.connect(self._load);self.combo.currentTextChanged.connect(self._preview);bus.ack.connect(self._ack);self._refresh()
    def _ack(self,k,v):self.values[str(k)]=v
    def _read_all(self):
        for p in self.params:self.transport.get_param(p.get("key",""))
    def _refresh(self):self.combo.clear();self.combo.addItems([p.stem for p in sorted(self.dir.glob("*.yaml"))])
    def _save(self):
        name=self.name.text().strip() or "profile";path=self.dir/(name+".yaml");obj={"vehicle":self.config.get("vehicle",{}),"parameters":self.values};path.write_text(yaml.safe_dump(obj,allow_unicode=True,sort_keys=False),encoding="utf-8");self._refresh();self.combo.setCurrentText(name)
    def _preview(self,name):
        p=self.dir/(name+".yaml");self.preview.setPlainText(p.read_text(encoding="utf-8") if p.exists() else "")
    def _load(self):
        p=self.dir/(self.combo.currentText()+".yaml")
        if not p.exists():return
        obj=yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        for k,v in (obj.get("parameters") or {}).items():
            try:self.transport.set_param(k,float(v))
            except Exception:pass
        QMessageBox.information(self,"参数方案","已开始下发；请在 ACK/协议监视器确认全部参数生效。")
