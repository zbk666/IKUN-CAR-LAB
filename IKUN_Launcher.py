from __future__ import annotations
import os
import sys
import subprocess
import importlib
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

ROOT = Path(__file__).resolve().parent
APP = ROOT / "CAR_LAB"
VENV = APP / ".venv"
VENV_PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

REQUIRED_MODULES = {
    "PySide6": "PySide6",
    "pyqtgraph": "pyqtgraph",
    "yaml": "yaml",
    "numpy": "numpy",
    "serial": "serial",
}
REQUIRED_FILES = [
    APP / "main.py",
    APP / "requirements.txt",
    APP / "vehicles",
    APP / "core",
    APP / "ui",
]

class Launcher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("IKUN CAR LAB")
        self.root.geometry("560x420")
        self.root.resizable(False, False)
        self.status = tk.StringVar(value="正在启动...")
        self.rows = {}
        self._build()

    def _build(self):
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="IKUN CAR LAB", font=("Arial", 20, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Universal Vehicle Tuning Platform", foreground="#666").pack(anchor="w", pady=(0,12))

        box = ttk.LabelFrame(outer, text="环境检测", padding=12)
        box.pack(fill="x")
        for key, label in [
            ("python", "Python / 运行环境"),
            ("deps", "Python 组件"),
            ("files", "CAR LAB 文件"),
            ("config", "车型与配置"),
        ]:
            row = ttk.Frame(box)
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=label, width=24).pack(side="left")
            v = ttk.Label(row, text="等待检查")
            v.pack(side="left")
            self.rows[key] = v

        ttk.Label(outer, textvariable=self.status, wraplength=520).pack(anchor="w", pady=(14,8))

        self.progress = ttk.Progressbar(outer, mode="determinate", maximum=100)
        self.progress.pack(fill="x")

        self.launch_btn = ttk.Button(outer, text="检查完成后启动 CAR LAB", command=self.launch, state="disabled")
        self.launch_btn.pack(anchor="e", pady=(14,0))

        ttk.Label(outer, text="日志目录：logs", foreground="#777").pack(anchor="w", pady=(18,0))

    def set_row(self, key, text, ok=None):
        prefix = "✓ " if ok is True else "✕ " if ok is False else ""
        self.rows[key].configure(text=prefix + text)

    def run(self, args, env=None, check=True):
        return subprocess.run(args, cwd=str(APP), env=env, check=check, capture_output=True, text=True)

    def find_python(self):
        candidates = []
        if VENV_PY.exists():
            candidates.append(str(VENV_PY))
        for cmd in ("py", "python"):
            from shutil import which
            p = which(cmd)
            if p: candidates.append(p)
        return candidates[0] if candidates else None

    def ensure_venv(self):
        if VENV_PY.exists():
            return str(VENV_PY)
        base = self.find_python()
        if not base:
            raise RuntimeError("未找到 Python。请安装 Python 3.10+ 后再次运行。")
        subprocess.run([base, "-m", "venv", str(VENV)], cwd=str(APP), check=True)
        return str(VENV_PY)

    def ensure_pip(self, py):
        try:
            subprocess.run([py, "-m", "pip", "--version"], check=True, capture_output=True, text=True)
        except Exception:
            subprocess.run([py, "-m", "ensurepip", "--upgrade"], check=True)

    def install_requirements(self, py):
        req = APP / "requirements.txt"
        mirrors = [
            ["-i", "https://pypi.tuna.tsinghua.edu.cn/simple"],
            [],
        ]
        last = None
        for extra in mirrors:
            try:
                subprocess.run(
                    [py, "-m", "pip", "install", "-r", str(req), *extra],
                    cwd=str(APP), check=True
                )
                return
            except subprocess.CalledProcessError as e:
                last = e
        raise RuntimeError("依赖安装失败，请查看 logs/launcher.log") from last

    def check_modules(self, py):
        missing = []
        code = (
            "import importlib.util,sys; "
            "mods=sys.argv[1:]; "
            "miss=[m for m in mods if importlib.util.find_spec(m) is None]; "
            "print('\\n'.join(miss)); sys.exit(1 if miss else 0)"
        )
        args = [py, "-c", code, *REQUIRED_MODULES.values()]
        p = subprocess.run(args, cwd=str(APP), capture_output=True, text=True)
        if p.returncode:
            missing = [x.strip() for x in p.stdout.splitlines() if x.strip()]
        return missing

    def validate_files(self):
        missing = [str(p.relative_to(ROOT)) for p in REQUIRED_FILES if not p.exists()]
        if missing:
            raise RuntimeError("缺少文件或目录：\n" + "\n".join(missing))

    def validate_vehicles(self, py):
        code = (
            "from core.config import list_vehicle_files,load_vehicle_config;"
            "fs=list_vehicle_files();"
            "assert fs,'vehicles 目录没有 YAML 车型配置';"
            "[load_vehicle_config(p) for p in fs];"
            "print(len(fs))"
        )
        p = subprocess.run([py, "-c", code], cwd=str(APP), capture_output=True, text=True)
        if p.returncode:
            raise RuntimeError("车型配置检查失败：\n" + (p.stderr or p.stdout))

    def scan(self):
        self.progress["value"] = 10
        self.set_row("files", "检查中...")
        self.validate_files()
        self.set_row("files", "文件完整", True)

        self.progress["value"] = 30
        py = self.ensure_venv()
        self.set_row("python", "运行环境正常", True)

        self.progress["value"] = 50
        self.ensure_pip(py)
        missing = self.check_modules(py)
        if missing:
            self.set_row("deps", "缺少组件，正在自动安装…")
            self.install_requirements(py)
            missing = self.check_modules(py)
            if missing:
                raise RuntimeError("以下组件仍缺失：\n" + "\n".join(missing))
        self.set_row("deps", "组件正常", True)

        self.progress["value"] = 75
        self.validate_vehicles(py)
        self.set_row("config", "车型配置正常", True)

        self.progress["value"] = 100
        self.status.set("环境检查完成，可以启动 CAR LAB。")
        self.launch_btn.configure(state="normal")

    def launch(self):
        try:
            py = self.ensure_venv()
            subprocess.Popen([py, str(APP/"main.py")], cwd=str(APP))
            self.root.after(300, self.root.destroy)
        except Exception as e:
            self.error(e)

    def error(self, exc):
        log = LOG_DIR / "launcher.log"
        log.write_text(
            "IKUN CAR LAB Launcher Error\n\n" + traceback.format_exc(),
            encoding="utf-8"
        )
        self.status.set("启动失败，详细信息已写入 logs/launcher.log")
        messagebox.showerror("IKUN CAR LAB 启动失败",
                             f"{exc}\n\n详细日志：{log}")

    def start(self):
        try:
            self.root.update_idletasks()
            self.scan()
        except Exception as e:
            self.error(e)
        self.root.mainloop()

if __name__ == "__main__":
    Launcher().start()
