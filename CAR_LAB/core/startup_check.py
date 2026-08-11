
from pathlib import Path
import sys, importlib

ROOT=Path(__file__).resolve().parents[1]
LOG_DIR=ROOT/"logs"
LOG_DIR.mkdir(parents=True,exist_ok=True)

def run_startup_checks():
    checks=[]
    required_modules=["PySide6","pyqtgraph","yaml","numpy","serial"]
    for mod in required_modules:
        try:
            m=importlib.import_module(mod)
            checks.append((mod,True,getattr(m,"__version__","installed")))
        except Exception as exc:
            checks.append((mod,False,str(exc)))
    checks.append(("main.py",(ROOT/"main.py").exists(),""))
    checks.append(("vehicles",(ROOT/"vehicles").exists(),""))
    checks.append(("requirements.txt",(ROOT/"requirements.txt").exists(),""))
    return checks

def format_checks(checks):
    lines=["IKUN CAR LAB 启动检查","="*60]
    ok=True
    for name,good,detail in checks:
        state="OK" if good else "FAIL"
        lines.append(f"[{state}] {name} {detail}")
        ok=ok and good
    return ok,"\n".join(lines)

def write_error_log(exc, context=""):
    LOG_DIR.mkdir(parents=True,exist_ok=True)
    p=LOG_DIR/"error.log"
    import traceback
    text=f"""IKUN CAR LAB Error Log
Python: {sys.executable}
Version: {sys.version}
Context: {context}

{traceback.format_exc()}
"""
    p.write_text(text,encoding="utf-8")
    return p
