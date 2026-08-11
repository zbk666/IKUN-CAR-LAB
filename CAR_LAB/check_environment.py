import sys
print("Python:", sys.executable)
for name in ("PySide6","pyqtgraph","yaml","serial","bleak"):
    try:
        mod=__import__(name); print(name, "OK", getattr(mod,"__version__",""))
    except Exception as e: print(name, "FAIL", e)
input("Press Enter to exit...")
