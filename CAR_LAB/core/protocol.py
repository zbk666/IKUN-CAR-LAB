import json

class JsonLineProtocol:
    def __init__(self, bus):
        self.bus = bus
        self.buffer = bytearray()

    def encode(self, obj):
        text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        self.bus.tx_text.emit(text)
        return (text + "\n").encode("utf-8")

    def feed(self, data: bytes):
        if not data:
            return
        self.buffer.extend(data)
        while b"\n" in self.buffer:
            line, _, rest = self.buffer.partition(b"\n")
            self.buffer = bytearray(rest)
            line = line.strip()
            if not line:
                continue
            text = line.decode("utf-8", errors="replace")
            self.bus.rx_text.emit(text)
            try:
                obj = json.loads(text)
            except json.JSONDecodeError:
                self.bus.event.emit("protocol_error", {"line": text})
                continue
            typ = obj.get("type")
            if typ == "TEL":
                d = obj.get("data") or {}
                if isinstance(d, dict):
                    self.bus.telemetry.emit(d)
            elif typ == "ACK":
                detail = {
                    "key": str(obj.get("key", "")),
                    "value": obj.get("value"),
                    "seq": obj.get("seq"),
                    "ok": bool(obj.get("ok", True)),
                    "error": obj.get("error"),
                    "raw": obj,
                }
                self.bus.ack.emit(detail["key"], detail["value"])
                self.bus.ack_detail.emit(detail)
            else:
                self.bus.event.emit(str(typ or "message"), obj)
