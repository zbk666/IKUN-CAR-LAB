
from pathlib import Path
import ast

ROOT=Path(__file__).resolve().parents[1]

QT_WIDGET_NAMES = {
    "QApplication","QWidget","QMainWindow","QFrame","QLabel","QPushButton",
    "QComboBox","QCheckBox","QSpinBox","QDoubleSpinBox","QLineEdit",
    "QPlainTextEdit","QTextEdit","QTableWidget","QTableWidgetItem",
    "QTreeWidget","QTreeWidgetItem","QHeaderView","QGroupBox","QGridLayout",
    "QHBoxLayout","QVBoxLayout","QFormLayout","QSplitter","QSlider","QMessageBox"
}

def imported_names(tree):
    names=set()
    for n in ast.walk(tree):
        if isinstance(n,ast.ImportFrom):
            for a in n.names:names.add(a.asname or a.name)
        elif isinstance(n,ast.Import):
            for a in n.names:names.add((a.asname or a.name.split(".")[0]))
    return names

def used_names(tree):
    return {n.id for n in ast.walk(tree) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load)}

issues=[]
for p in (ROOT/"ui").glob("*.py"):
    try: tree=ast.parse(p.read_text(encoding="utf-8"))
    except SyntaxError as e:
        issues.append((p.name,"syntax",str(e))); continue
    imported=imported_names(tree)
    used=used_names(tree)
    for name in sorted((used & QT_WIDGET_NAMES)-imported):
        issues.append((p.name,"missing_qt_import",name))

print("PASS" if not issues else "FAIL")
for x in issues: print(x)
raise SystemExit(1 if issues else 0)
