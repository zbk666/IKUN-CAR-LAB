from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
import pyqtgraph as pg


DARK_STYLE = r'''
QWidget { background:#0b1017; color:#e7edf5; font-family:"Microsoft YaHei UI","Segoe UI"; font-size:13px; }
QMainWindow { background:#080d13; }
QFrame#header, QFrame#panel, QFrame#toolbar, QFrame#plotPanel, QFrame#card {
    background:#111923; border:1px solid #223044; border-radius:10px;
}
QFrame#sidebar { background:#0e151e; border-right:1px solid #202c3b; }
QLabel#brandIKUN { font-size:24px; font-weight:900; font-style:italic; letter-spacing:1px; color:#f6f9fc; }
QLabel#subtitle, QLabel#muted { color:#8494a7; }
QLabel#panelTitle { color:#d9e6f3; font-size:14px; font-weight:700; }
QLabel#scopeTime { color:#7ec8ff; font-size:18px; font-weight:700; }
QLabel#pageTitle { color:#f3f7fb; font-size:18px; font-weight:750; }
QLabel#statusGood { color:#78d79a; background:#10281b; border:1px solid #245d3b; border-radius:11px; padding:3px 9px; }
QLabel#statusBad { color:#ff9c99; background:#2c1517; border:1px solid #683034; border-radius:11px; padding:3px 9px; }
QPushButton { background:#182433; border:1px solid #304157; border-radius:7px; padding:7px 11px; color:#e7edf5; }
QPushButton:hover { background:#203149; border-color:#45607d; }
QPushButton:pressed { background:#14202e; }
QPushButton:checked { background:#263e5c; border-color:#4c82b8; }
QPushButton#primary { background:#176ca4; border-color:#2b8ac5; font-weight:700; }
QPushButton#primary:hover { background:#1e7bb8; }
QPushButton#danger { background:#67252b; border-color:#a23b45; font-weight:700; }
QPushButton#danger:hover { background:#7d2c34; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget, QTextEdit, QPlainTextEdit {
    background:#0c131c; border:1px solid #2a3a4f; border-radius:7px; padding:5px; selection-background-color:#245a86;
}
QComboBox::drop-down { border:0; width:24px; }
QTableWidget { gridline-color:#1f2a38; alternate-background-color:#0f1721; }
QHeaderView::section { background:#172231; color:#aebdcb; padding:6px; border:0; border-bottom:1px solid #2b394a; }
QGroupBox { border:1px solid #263548; border-radius:9px; margin-top:12px; padding-top:9px; font-weight:650; }
QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 5px; color:#aebed0; }
QTreeWidget { background:transparent; border:0; outline:0; padding:5px; }
QTreeWidget::item { height:35px; border-radius:7px; padding-left:4px; color:#aebdcc; }
QTreeWidget::item:hover { background:#152131; color:#eef5fb; }
QTreeWidget::item:selected { background:#1a3954; color:#ffffff; }
QSplitter::handle { background:#111923; width:4px; }
QScrollBar:vertical { background:#0b1119; width:10px; margin:0; }
QScrollBar::handle:vertical { background:#2c3d50; min-height:26px; border-radius:5px; }
QScrollBar:horizontal { background:#0b1119; height:10px; }
QScrollBar::handle:horizontal { background:#2c3d50; min-width:26px; border-radius:5px; }
'''


LIGHT_STYLE = r'''
QWidget { background:#f5f6f8; color:#20242a; font-family:"Microsoft YaHei UI","Segoe UI"; font-size:13px; }
QMainWindow { background:#eef1f4; }
QFrame#header, QFrame#panel, QFrame#toolbar, QFrame#plotPanel, QFrame#card {
    background:#ffffff; border:1px solid #d7dce2; border-radius:9px;
}
QFrame#sidebar { background:#ffffff; border-right:1px solid #d7dce2; }
QLabel#brandIKUN { font-size:24px; font-weight:900; font-style:italic; letter-spacing:1px; color:#111827; }
QLabel#subtitle, QLabel#muted { color:#68727f; }
QLabel#panelTitle { color:#25313d; font-size:14px; font-weight:700; }
QLabel#scopeTime { color:#116da8; font-size:18px; font-weight:700; }
QLabel#pageTitle { color:#15191e; font-size:18px; font-weight:750; }
QLabel#statusGood { color:#18733b; background:#edf9f1; border:1px solid #9bd2ad; border-radius:11px; padding:3px 9px; }
QLabel#statusBad { color:#a62731; background:#fff1f2; border:1px solid #e2a8ad; border-radius:11px; padding:3px 9px; }
QPushButton { background:#ffffff; border:1px solid #cbd2da; border-radius:6px; padding:7px 11px; color:#20242a; }
QPushButton:hover { background:#f1f5f9; border-color:#aeb8c3; }
QPushButton:pressed { background:#e8edf2; }
QPushButton:checked { background:#e5f2fb; border-color:#6da8cf; color:#0b5f91; }
QPushButton#primary { background:#1674ae; border-color:#1674ae; color:#ffffff; font-weight:700; }
QPushButton#primary:hover { background:#0f659a; }
QPushButton#danger { background:#c33c46; border-color:#b4313b; color:#ffffff; font-weight:700; }
QPushButton#danger:hover { background:#ab2e37; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget, QTextEdit, QPlainTextEdit {
    background:#ffffff; color:#20242a; border:1px solid #cfd6de; border-radius:6px; padding:5px; selection-background-color:#b9dcf2;
}
QComboBox::drop-down { border:0; width:24px; }
QTableWidget { gridline-color:#e0e4e9; alternate-background-color:#f7f9fb; }
QHeaderView::section { background:#f0f3f6; color:#3a4652; padding:6px; border:0; border-bottom:1px solid #d5dbe2; }
QGroupBox { border:1px solid #d5dbe2; border-radius:8px; margin-top:12px; padding-top:9px; font-weight:650; background:#ffffff; }
QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 5px; color:#3b4651; }
QTreeWidget { background:transparent; border:0; outline:0; padding:5px; }
QTreeWidget::item { height:35px; border-radius:6px; padding-left:4px; color:#4b5560; }
QTreeWidget::item:hover { background:#f0f4f8; color:#12171d; }
QTreeWidget::item:selected { background:#dcedf8; color:#0b5f91; }
QSplitter::handle { background:#e7eaee; width:4px; }
QScrollBar:vertical { background:#f1f3f5; width:10px; margin:0; }
QScrollBar::handle:vertical { background:#bdc5ce; min-height:26px; border-radius:5px; }
QScrollBar:horizontal { background:#f1f3f5; height:10px; }
QScrollBar::handle:horizontal { background:#bdc5ce; min-width:26px; border-radius:5px; }
'''


THEME_STYLES = {"黑色": DARK_STYLE, "白色": LIGHT_STYLE}

PLOT_THEMES = {
    "黑色": {"bg": "#0a0f16", "fg": "#b9c4d0", "axis": "#5f6c79"},
    "白色": {"bg": "#ffffff", "fg": "#30363d", "axis": "#7b8794"},
}


def apply_plot_theme(root, theme_name: str):
    cfg = PLOT_THEMES.get(theme_name, PLOT_THEMES["黑色"])
    fg = QColor(cfg["fg"])
    axis_color = QColor(cfg["axis"])
    for plot in root.findChildren(pg.PlotWidget):
        plot.setBackground(cfg["bg"])
        item = plot.getPlotItem()
        for axis_name in ("left", "right", "bottom", "top"):
            try:
                axis = item.getAxis(axis_name)
                axis.setPen(pg.mkPen(axis_color))
                axis.setTextPen(pg.mkPen(fg))
            except Exception:
                pass
        try:
            item.titleLabel.item.setDefaultTextColor(fg)
        except Exception:
            pass
        try:
            if item.legend:
                for _sample, label in item.legend.items:
                    label.item.setDefaultTextColor(fg)
        except Exception:
            pass


def make_ikun_icon(theme_name: str) -> QIcon:
    light = theme_name == "白色"
    pix = QPixmap(192, 192)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    bg = QColor("#ffffff" if light else "#101820")
    fg = QColor("#111827" if light else "#f8fafc")
    painter.setBrush(bg)
    painter.setPen(QColor("#cdd3da" if light else "#304255"))
    painter.drawRoundedRect(7, 7, 178, 178, 34, 34)
    font = QFont("Arial", 42, QFont.Weight.Black)
    font.setItalic(True)
    painter.setFont(font)
    painter.setPen(fg)
    painter.drawText(pix.rect(), 0x84, "IKUN")  # AlignCenter
    painter.end()
    return QIcon(pix)
