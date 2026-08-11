from PySide6.QtCore import QObject, Signal

class DataBus(QObject):
    telemetry = Signal(dict)
    ack = Signal(str, object)                 # legacy
    ack_detail = Signal(dict)                 # seq/ok/error
    rx_text = Signal(str)
    tx_text = Signal(str)
    connection = Signal(bool, str)
    parameter_changed = Signal(str, object, object)
    parameter_sync = Signal(dict)
    event = Signal(str, dict)
