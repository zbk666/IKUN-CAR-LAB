import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from core.config import load_vehicle_config
from core.bus import DataBus
from core.protocol import JsonLineProtocol
from core.transport import TransportManager
from core.startup_check import run_startup_checks, format_checks, write_error_log
from ui.main_window import MainWindow

def main():
    app=QApplication(sys.argv)
    app.setApplicationName("IKUN CAR LAB v1.6.0")

    checks=run_startup_checks()
    ok, report=format_checks(checks)
    failed=[x for x in checks if not x[1]]
    if failed:
        print(report)
        QMessageBox.critical(None,"CAR LAB 启动检查失败",report)
        return 2

    try:
        config=load_vehicle_config()
        bus=DataBus()
        protocol=JsonLineProtocol(bus)
        transport=TransportManager(bus,protocol,config)
        win=MainWindow(bus,transport,config)
        win.resize(1500,920)
        win.show()
        return app.exec()
    except Exception as exc:
        log=write_error_log(exc, context=report)
        QMessageBox.critical(None,"CAR LAB 启动失败",
                             f"软件启动失败。\n\n详细错误已保存：\n{log}")
        print(report)
        raise

if __name__=="__main__":
    sys.exit(main())
