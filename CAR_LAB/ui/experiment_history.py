from __future__ import annotations
import csv, json, time
from pathlib import Path
import pyqtgraph as pg
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QTableWidget,QTableWidgetItem,QPushButton,QPlainTextEdit,QFileDialog,QMessageBox,QAbstractItemView
from core.history_store import HistoryStore


class ExperimentHistoryPage(QWidget):
    def __init__(self,bus,transport,config):
        super().__init__();self.store=HistoryStore();self.current_id=None
        root=QVBoxLayout(self);row=QHBoxLayout();refresh=QPushButton("刷新");export=QPushButton("导出当前 CSV");delete=QPushButton("删除当前记录");refresh.clicked.connect(self._refresh);export.clicked.connect(self._export);delete.clicked.connect(self._delete);row.addWidget(refresh);row.addWidget(export);row.addWidget(delete);row.addStretch();root.addLayout(row)
        self.table=QTableWidget(0,6);self.table.setHorizontalHeaderLabels(["ID","时间","类型","名称","车型","备注"]);self.table.setSelectionBehavior(QAbstractItemView.SelectRows);self.table.itemSelectionChanged.connect(self._select);root.addWidget(self.table,1)
        self.plot=pg.PlotWidget(title="实验曲线（支持 speed_step 记录）");self.plot.showGrid(x=True,y=True,alpha=.2);self.plot.addLegend();root.addWidget(self.plot,1)
        self.detail=QPlainTextEdit();self.detail.setReadOnly(True);root.addWidget(self.detail,1);self._refresh()
    def _refresh(self):
        rows=self.store.list(limit=300);self.table.setRowCount(len(rows));
        for r,d in enumerate(rows):
            vals=[d["id"],time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(d["created_at"])),d["kind"],d["name"],d.get("vehicle","") or "",d.get("notes","") or ""]
            for c,v in enumerate(vals):self.table.setItem(r,c,QTableWidgetItem(str(v)))
    def _select(self):
        r=self.table.currentRow()
        if r<0:return
        self.current_id=int(self.table.item(r,0).text());d=self.store.get(self.current_id);self.plot.clear()
        if not d:return
        self.detail.setPlainText(json.dumps({"parameters":d.get("parameters",{}),"metrics":d.get("metrics",{}),"notes":d.get("notes","")},ensure_ascii=False,indent=2))
        s=d.get("samples",[]) or []
        if s and "t" in s[0]:
            x=[float(z.get("t",i)) for i,z in enumerate(s)]
            for k in ("target","actual","output"):
                if any(k in z for z in s):self.plot.plot(x,[float(z.get(k,0)) for z in s],name=k)
    def _export(self):
        if not self.current_id:return
        d=self.store.get(self.current_id);s=d.get("samples",[]) if d else []
        if not s: QMessageBox.information(self,"导出","当前记录没有逐点 samples。");return
        path,_=QFileDialog.getSaveFileName(self,"导出 CSV",f"experiment_{self.current_id}.csv","CSV (*.csv)")
        if not path:return
        keys=sorted({k for z in s for k in z})
        with open(path,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(s)
    def _delete(self):
        if not self.current_id:return
        self.store.delete(self.current_id);self.current_id=None;self.plot.clear();self.detail.clear();self._refresh()
