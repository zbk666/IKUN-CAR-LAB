import json
import math
import socket
import time
from collections import deque
from PySide6.QtCore import QObject, QTimer

try:
    import serial
except Exception:
    serial = None

from core.angle import angle_error_deg, wrap_deg
from core.ble_transport import BleLink, scan_ble_devices


def _virtual_track_curvature(progress: float) -> float:
    """Signed virtual curvature for simulator corner-analysis demos.

    Straight sections are exactly zero; four smooth corners alternate left/right.
    The exact value is illustrative rather than a physical track model.
    """
    p = float(progress) % 1.0
    sections = [
        (0.10, 0.22, 0.34),
        (0.34, 0.48, -0.46),
        (0.60, 0.74, 0.28),
        (0.84, 0.96, -0.38),
    ]
    for start, end, amplitude in sections:
        if start <= p <= end:
            phase = (p - start) / (end - start)
            return amplitude * math.sin(math.pi * phase)
    return 0.0


class TransportManager(QObject):
    def __init__(self, bus, protocol, config):
        super().__init__()
        self.bus = bus
        self.protocol = protocol
        self.config = config
        self.kind = None
        self.serial_obj = None
        self.sock = None
        self.ble_link = BleLink()
        self.connected = False
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll)
        self.poll_timer.start(10)
        self.sim_timer = QTimer(self)
        self.sim_timer.timeout.connect(self._sim_tick)
        self.sim_dt = 0.02
        self.sim = self._new_sim_state()
        self._last_sim_tel = 0.0
        self.param_cache = {}
        self._param_seq = 0
        self._param_inflight = None
        self._param_set_pending = {}
        self._param_set_order = deque()
        self._param_get_pending = deque()
        self._param_get_set = set()
        self._param_timeout_s = 0.60
        self._param_max_retries = 3
        self._param_backoff_until = 0.0
        self.bus.ack.connect(self._cache_ack)
        self.bus.ack_detail.connect(self._handle_ack_detail)

    def _new_sim_state(self):
        return {
            "target_rpm": 0.0,
            "actual_rpm": 0.0,
            "speed": 0.0,
            "motor_pwm": 0.0,
            "target_yaw": 0.0,
            "yaw": 0.0,
            "target_yaw_rate": 0.0,
            "gyro_z": 0.0,
            "steering_output": 0.0,
            "battery": 12.4,
            "left_current": 0.0,
            "right_current": 0.0,
            "left_rpm": 0.0,
            "right_rpm": 0.0,
            "left_encoder": 0.0,
            "right_encoder": 0.0,
            "track_progress": 0.0,
            "lap_index": 0,
            "custom_target": 0.0,
            "custom_feedback": 0.0,
            "custom_output": 0.0,
            "custom_i": 0.0,
            "params": {
                "speed_kp": 0.85, "speed_ki": 0.10, "speed_kd": 0.01,
                "heading_kp": 2.4, "heading_ki": 0.0, "heading_kd": 0.12,
                "yaw_rate_kp": 0.85, "yaw_rate_ki": 0.06, "yaw_rate_kd": 0.01,
                "left_motor_kp": 1.0, "left_motor_ki": 0.1, "left_motor_kd": 0.0,
                "right_motor_kp": 1.0, "right_motor_ki": 0.1, "right_motor_kd": 0.0,
                "custom_kp": 1.2, "custom_ki": 0.08, "custom_kd": 0.0,
            },
            "speed_i": 0.0,
            "yaw_i": 0.0,
            "rate_i": 0.0,
        }

    def connect_sim(self):
        self.disconnect()
        self.kind = "sim"
        self.connected = True
        self.sim = self._new_sim_state()
        self.sim_timer.start(int(self.sim_dt * 1000))
        self.bus.connection.emit(True, "仿真车已连接")
        self._service_param_queue()

    def scan_ble(self, timeout=4.0):
        return scan_ble_devices(timeout)

    def connect_ble(self, address, write_uuid, notify_uuid, auto_reconnect=True):
        self.disconnect()
        self.kind = "ble"
        try:
            self.ble_link.start(address, write_uuid, notify_uuid, auto_reconnect=auto_reconnect)
        except Exception:
            self.ble_link.stop()
            self.kind = None
            self.connected = False
            raise
        self.connected = True
        self.bus.connection.emit(True, f"BLE {address}")
        self._service_param_queue()

    def connect_serial(self, port, baud, label="串口"):
        self.disconnect()
        if serial is None:
            raise RuntimeError("未安装 pyserial")
        self.serial_obj = serial.Serial(port, int(baud), timeout=0)
        self.kind = "serial"
        self.connected = True
        self.bus.connection.emit(True, f"{label} {port} @ {baud}")
        self._service_param_queue()

    def connect_tcp(self, host, port):
        self.disconnect()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect((host, int(port)))
        s.setblocking(False)
        self.sock = s
        self.kind = "tcp"
        self.connected = True
        self.bus.connection.emit(True, f"TCP {host}:{port}")
        self._service_param_queue()

    def disconnect(self):
        self.sim_timer.stop()
        if self.serial_obj is not None:
            try: self.serial_obj.close()
            except Exception: pass
        if self.sock is not None:
            try: self.sock.close()
            except Exception: pass
        if self.kind == "ble" or self.ble_link.thread is not None:
            try: self.ble_link.stop()
            except Exception: pass
        self.serial_obj = None
        self.sock = None
        was = self.connected
        self.connected = False
        self.kind = None
        if was:
            self.bus.connection.emit(False, "已断开")

    def send_obj(self, obj):
        if not self.connected:
            self.bus.event.emit("transport_error", {"message": "尚未连接车辆"})
            return
        raw = self.protocol.encode(obj)
        if self.kind == "sim":
            self._sim_receive(obj)
        elif self.kind == "serial":
            self.serial_obj.write(raw)
        elif self.kind == "tcp":
            self.sock.sendall(raw)
        elif self.kind == "ble":
            self.ble_link.send(raw)

    def set_param(self, key, value):
        key = str(key); value = float(value)
        old = self.param_cache.get(key, "?")
        self.param_cache[key] = value
        self.bus.parameter_changed.emit(key, old, value)
        self._param_set_pending[key] = value
        if key not in self._param_set_order and not (self._param_inflight and self._param_inflight.get("key") == key):
            self._param_set_order.append(key)
        self.bus.parameter_sync.emit({
            "key": key, "value": value, "state": "queued",
            "seq": None, "retry": 0, "message": "已进入参数发送缓冲区"
        })
        self._service_param_queue()

    def _cache_ack(self, key, value):
        self.param_cache[str(key)] = value

    def _handle_ack_detail(self, detail):
        op = self._param_inflight
        if not op:
            return
        key = str(detail.get("key", ""))
        seq_match = detail.get("seq") is not None and str(detail.get("seq")) == str(op.get("seq"))
        if not (seq_match or key == op["key"]):
            return
        if not detail.get("ok", True):
            self.bus.parameter_sync.emit({
                "key": op["key"], "value": op.get("value"), "state": "retry",
                "seq": op["seq"], "retry": op["retry"], "message": str(detail.get("error") or "MCU拒绝参数")
            })
            self._retry_or_defer()
            return
        if op["kind"] == "SET" and detail.get("value") is not None:
            try:
                desired = float(op["value"]); actual = float(detail["value"])
                tol = max(1e-6, abs(desired) * 1e-5)
                if abs(actual - desired) > tol:
                    self.bus.parameter_sync.emit({
                        "key": op["key"], "value": desired, "actual": actual,
                        "state": "mismatch", "seq": op["seq"], "retry": op["retry"],
                        "message": "ACK回读值与目标值不一致"
                    })
                    self._retry_or_defer()
                    return
                self.param_cache[op["key"]] = actual
            except Exception:
                self.param_cache[op["key"]] = op["value"]
        elif op["kind"] == "SET":
            self.param_cache[op["key"]] = op["value"]
        self.bus.parameter_sync.emit({
            "key": op["key"], "value": op.get("value"), "state": "acked",
            "seq": op["seq"], "retry": op["retry"], "message": "MCU已确认"
        })
        self._param_inflight = None
        self._param_backoff_until = 0.0
        self._service_param_queue()

    def _next_param_seq(self):
        self._param_seq = (self._param_seq + 1) & 0xFFFFFFFF
        if self._param_seq == 0: self._param_seq = 1
        return self._param_seq

    def _send_inflight(self):
        op=self._param_inflight
        if not op or not self.connected: return
        obj={"type":op["kind"],"key":op["key"],"seq":op["seq"]}
        if op["kind"]=="SET": obj["value"]=op["value"]
        self.send_obj(obj)
        op["sent_at"]=time.monotonic()
        self.bus.parameter_sync.emit({
            "key":op["key"],"value":op.get("value"),"state":"sending",
            "seq":op["seq"],"retry":op["retry"],"message":f'{op["kind"]} 已发送，等待 ACK'
        })

    def _start_next_param_op(self):
        if self._param_inflight or not self.connected or time.monotonic() < self._param_backoff_until: return
        while self._param_set_order:
            key=self._param_set_order.popleft()
            if key not in self._param_set_pending: continue
            val=self._param_set_pending.pop(key)
            self._param_inflight={"kind":"SET","key":key,"value":val,"seq":self._next_param_seq(),"retry":0,"sent_at":0.0}
            self._send_inflight(); return
        while self._param_get_pending:
            key=self._param_get_pending.popleft()
            self._param_get_set.discard(key)
            if key in self._param_set_pending:
                self._param_get_pending.append(key); self._param_get_set.add(key); return
            self._param_inflight={"kind":"GET","key":key,"value":None,"seq":self._next_param_seq(),"retry":0,"sent_at":0.0}
            self._send_inflight(); return

    def _retry_or_defer(self):
        op=self._param_inflight
        if not op: return
        if op["retry"] < self._param_max_retries:
            op["retry"] += 1
            self._send_inflight()
            return
        if op["kind"]=="SET":
            self._param_set_pending[op["key"]]=op["value"]
            if op["key"] not in self._param_set_order: self._param_set_order.append(op["key"])
        else:
            if op["key"] not in self._param_get_set:
                self._param_get_pending.append(op["key"]); self._param_get_set.add(op["key"])
        self.bus.parameter_sync.emit({
            "key":op["key"],"value":op.get("value"),"state":"deferred",
            "seq":op["seq"],"retry":op["retry"],"message":"ACK超时，保留在缓冲区，稍后自动重试"
        })
        self._param_inflight=None
        self._param_backoff_until=time.monotonic()+1.0
        self._service_param_queue()

    def _service_param_timeout(self):
        op=self._param_inflight
        if op and self.connected and time.monotonic()-op["sent_at"] >= self._param_timeout_s:
            self.bus.parameter_sync.emit({
                "key":op["key"],"value":op.get("value"),"state":"timeout",
                "seq":op["seq"],"retry":op["retry"],"message":"等待 ACK 超时"
            })
            self._retry_or_defer()

    def _service_param_queue(self):
        self._start_next_param_op()

    def get_param(self, key):
        key=str(key)
        if key not in self._param_get_set:
            self._param_get_pending.append(key); self._param_get_set.add(key)
            self.bus.parameter_sync.emit({
                "key":key,"value":None,"state":"queued","seq":None,"retry":0,
                "message":"读取请求已进入参数缓冲区"
            })
        self._service_param_queue()

    def command(self, key, value):
        self.send_obj({"type": "CMD", "key": str(key), "value": value})

    def _poll(self):
        self._service_param_timeout()
        self._service_param_queue()
        # BLE events must be polled even during a reconnect period where connected=False.
        if self.kind == "ble":
            for event, message in self.ble_link.poll_events():
                if event == "connected":
                    self.connected = True
                    self.bus.connection.emit(True, message)
                elif event in ("disconnected", "reconnecting"):
                    self.connected = False
                    self.bus.connection.emit(False, message)
                elif event == "error":
                    self.bus.event.emit("transport_error", {"message": message})
            for chunk in self.ble_link.poll_rx():
                self.protocol.feed(chunk)
        if not self.connected:
            return
        try:
            if self.kind == "serial" and self.serial_obj:
                n = self.serial_obj.in_waiting
                if n:
                    self.protocol.feed(self.serial_obj.read(n))
            elif self.kind == "tcp" and self.sock:
                try:
                    data = self.sock.recv(65536)
                    if data:
                        self.protocol.feed(data)
                except BlockingIOError:
                    pass
        except Exception as e:
            self.bus.event.emit("transport_error", {"message": str(e)})

    def _emit_sim_obj(self, obj):
        raw = (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        self.protocol.feed(raw)

    def _sim_receive(self, obj):
        typ = obj.get("type")
        key = str(obj.get("key", ""))
        value = obj.get("value")
        if typ == "SET":
            self.sim["params"][key] = float(value)
            self._emit_sim_obj({"type": "ACK", "key": key, "value": float(value), "seq": obj.get("seq"), "ok": True})
        elif typ == "GET":
            val = self.sim["params"].get(key, 0.0)
            self._emit_sim_obj({"type": "ACK", "key": key, "value": val, "seq": obj.get("seq"), "ok": True})
        elif typ == "CMD":
            if key in ("target_rpm", "speed_target_rpm"):
                self.sim["target_rpm"] = float(value)
            elif key.endswith("_rpm_target"):
                self.sim["target_rpm"] = float(value)
            elif key in ("target_yaw", "heading_target"):
                self.sim["target_yaw"] = wrap_deg(float(value))
            elif key == "custom_target":
                self.sim["custom_target"] = float(value)
            elif key == "save_parameters":
                pass
            elif key == "emergency_stop":
                self.sim["target_rpm"] = 0.0
                self.sim["motor_pwm"] = 0.0
            elif key.endswith("motor"):
                self.sim["motor_pwm"] = float(value)
            self._emit_sim_obj({"type": "ACK", "key": key, "value": value})

    def _sim_tick(self):
        s = self.sim
        p = s["params"]
        dt = self.sim_dt

        speed_err = s["target_rpm"] - s["actual_rpm"]
        s["speed_i"] = max(-5000, min(5000, s["speed_i"] + speed_err * dt))
        drive = p.get("speed_kp", 0.8) * speed_err + p.get("speed_ki", 0.0) * s["speed_i"]
        s["motor_pwm"] = max(-100.0, min(100.0, drive / 8.0))
        tau = max(0.06, 0.35 / max(0.2, p.get("speed_kp", 0.8)))
        s["actual_rpm"] += (s["target_rpm"] - s["actual_rpm"]) * dt / tau
        s["actual_rpm"] += math.sin(time.monotonic() * 7.0) * 0.18
        s["speed"] = s["actual_rpm"] * 0.0032

        e_yaw = angle_error_deg(s["target_yaw"], s["yaw"])
        s["yaw_i"] = max(-100, min(100, s["yaw_i"] + e_yaw * dt))
        rate_cmd = p.get("heading_kp", 2.4) * e_yaw + p.get("heading_ki", 0.0) * s["yaw_i"]
        speed_factor = 1.0 + max(0.0, abs(s["speed"]) - 1.0) * 0.16
        s["target_yaw_rate"] = max(-180, min(180, rate_cmd / speed_factor))

        rate_err = s["target_yaw_rate"] - s["gyro_z"]
        s["rate_i"] = max(-300, min(300, s["rate_i"] + rate_err * dt))
        steering = p.get("yaw_rate_kp", 0.85) * rate_err + p.get("yaw_rate_ki", 0.06) * s["rate_i"]
        s["steering_output"] = max(-100, min(100, steering))
        rate_tau = max(0.04, 0.24 / max(0.2, p.get("yaw_rate_kp", 0.85)))
        desired_rate = s["target_yaw_rate"] + 0.10 * s["steering_output"]
        s["gyro_z"] += (desired_rate - s["gyro_z"]) * dt / rate_tau
        s["yaw"] = wrap_deg(s["yaw"] + s["gyro_z"] * dt)

        custom_err = s["custom_target"] - s["custom_feedback"]
        s["custom_i"] = max(-10000, min(10000, s["custom_i"] + custom_err * dt))
        s["custom_output"] = max(-100.0, min(100.0, p.get("custom_kp", 1.2) * custom_err + p.get("custom_ki", 0.08) * s["custom_i"]))
        custom_tau = max(0.05, 0.5 / max(0.2, abs(p.get("custom_kp", 1.2))))
        s["custom_feedback"] += (s["custom_target"] - s["custom_feedback"]) * dt / custom_tau

        s["left_rpm"] = s["actual_rpm"] - s["steering_output"] * 0.55
        s["right_rpm"] = s["actual_rpm"] + s["steering_output"] * 0.55
        s["left_encoder"] += s["left_rpm"] / 60.0 * 1024.0 * dt
        s["right_encoder"] += s["right_rpm"] / 60.0 * 1024.0 * dt
        load = abs(s["motor_pwm"]) / 100.0
        s["left_current"] = 0.25 + 2.0 * load + abs(s["steering_output"]) * 0.003
        s["right_current"] = 0.24 + 1.9 * load + abs(s["steering_output"]) * 0.003
        s["battery"] = max(10.0, 12.4 - 0.85 * load - 0.10 * abs(s["steering_output"]) / 100.0)
        battery_raw = int(max(0, min(4095, (s["battery"] / 4.0) / 3.3 * 4095)))

        # lightweight virtual track: 0..1 progress, one-sample lap_trigger pulse
        prev_progress = s["track_progress"]
        s["track_progress"] = (s["track_progress"] + abs(s["speed"]) * dt / 18.0) % 1.0
        lap_trigger = 1 if s["track_progress"] < prev_progress else 0
        if lap_trigger: s["lap_index"] += 1
        curvature = _virtual_track_curvature(s["track_progress"])
        tracking_error = 0.012 * math.sin(time.monotonic()*2.3) + 0.0008*abs(s["steering_output"])

        tel = {
            "target_rpm": round(s["target_rpm"], 3),
            "actual_rpm": round(s["actual_rpm"], 3),
            "speed_error": round(speed_err, 3),
            "motor_pwm": round(s["motor_pwm"], 3),
            "speed": round(s["speed"], 4),
            "target_yaw": round(s["target_yaw"], 3),
            "yaw": round(s["yaw"], 3),
            "yaw_error": round(e_yaw, 3),
            "target_yaw_rate": round(s["target_yaw_rate"], 3),
            "gyro_z": round(s["gyro_z"], 3),
            "steering_output": round(s["steering_output"], 3),
            "battery": round(s["battery"], 3),
            "battery_raw": battery_raw,
            "left_current": round(s["left_current"], 3),
            "right_current": round(s["right_current"], 3),
            "left_rpm": round(s["left_rpm"], 3),
            "right_rpm": round(s["right_rpm"], 3),
            "left_encoder": int(s["left_encoder"]),
            "right_encoder": int(s["right_encoder"]),
            "left_pwm": round(s["motor_pwm"] - s["steering_output"]*0.15, 3),
            "right_pwm": round(s["motor_pwm"] + s["steering_output"]*0.15, 3),
            # four-motor aliases keep the built-in four-wheel vehicle template usable
            "front_left_rpm": round(s["left_rpm"] * 1.01, 3),
            "rear_left_rpm": round(s["left_rpm"] * 0.99, 3),
            "front_right_rpm": round(s["right_rpm"] * 1.005, 3),
            "rear_right_rpm": round(s["right_rpm"] * 0.995, 3),
            "front_left_encoder": int(s["left_encoder"] * 1.01),
            "rear_left_encoder": int(s["left_encoder"] * 0.99),
            "front_right_encoder": int(s["right_encoder"] * 1.005),
            "rear_right_encoder": int(s["right_encoder"] * 0.995),
            "front_left_current": round(s["left_current"] * 1.02, 3),
            "rear_left_current": round(s["left_current"] * 0.98, 3),
            "front_right_current": round(s["right_current"] * 1.01, 3),
            "rear_right_current": round(s["right_current"] * 0.99, 3),
            "front_left_pwm": round(s["motor_pwm"] - s["steering_output"]*0.15, 3),
            "rear_left_pwm": round(s["motor_pwm"] - s["steering_output"]*0.15, 3),
            "front_right_pwm": round(s["motor_pwm"] + s["steering_output"]*0.15, 3),
            "rear_right_pwm": round(s["motor_pwm"] + s["steering_output"]*0.15, 3),
            "tracking_error": round(tracking_error, 5),
            "track_progress": round(s["track_progress"], 5),
            "curvature": round(curvature, 5),
            "lap_trigger": lap_trigger,
            "custom_target": round(s["custom_target"], 4),
            "custom_feedback": round(s["custom_feedback"], 4),
            "custom_error": round(custom_err, 4),
            "custom_output": round(s["custom_output"], 4),
        }
        self._emit_sim_obj({"type": "TEL", "data": tel})
