import asyncio
import queue
import threading
import time

try:
    from bleak import BleakClient, BleakScanner
except Exception:
    BleakClient = None
    BleakScanner = None


class BleUnavailable(RuntimeError):
    pass


def scan_ble_devices(timeout=4.0):
    """Blocking BLE scan used by the small connection dialog."""
    if BleakScanner is None:
        raise BleUnavailable("未安装 bleak，请先执行 install.bat 或 pip install bleak")

    async def _scan():
        devices = await BleakScanner.discover(timeout=float(timeout))
        result = []
        for dev in devices:
            name = getattr(dev, "name", None) or "(未命名设备)"
            address = getattr(dev, "address", "")
            if address:
                result.append((name, address))
        return result

    return asyncio.run(_scan())


class BleLink:
    """BLE GATT byte pipe.

    Incoming notifications are buffered and later drained by Qt's polling timer,
    so the protocol parser always runs in the GUI thread. Outgoing data is queued
    and written by the BLE asyncio thread. JSON Lines may be split over BLE packets;
    JsonLineProtocol already supports arbitrary chunking.
    """

    def __init__(self):
        self.rx_queue = queue.Queue()
        self.tx_queue = queue.Queue(maxsize=500)
        self.event_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.first_connected = threading.Event()
        self.thread = None
        self.address = ""
        self.write_uuid = ""
        self.notify_uuid = ""
        self.auto_reconnect = True
        self.chunk_size = 20

    @staticmethod
    def available():
        return BleakClient is not None

    def start(self, address, write_uuid, notify_uuid, auto_reconnect=True, timeout=8.0):
        if BleakClient is None:
            raise BleUnavailable("未安装 bleak，请先执行 install.bat 或 pip install bleak")
        self.stop()
        self.address = str(address).strip()
        self.write_uuid = str(write_uuid).strip()
        self.notify_uuid = str(notify_uuid).strip()
        if not self.address or not self.write_uuid or not self.notify_uuid:
            raise ValueError("BLE 地址、Write UUID、Notify UUID 都不能为空")
        self.auto_reconnect = bool(auto_reconnect)
        self.stop_event.clear()
        self.first_connected.clear()
        self.thread = threading.Thread(target=self._thread_main, name="CARLAB-BLE", daemon=True)
        self.thread.start()
        if not self.first_connected.wait(float(timeout)):
            # Keep worker alive for automatic reconnect, but make first connection failure explicit.
            raise TimeoutError("BLE 首次连接超时。请检查设备地址、UUID 和设备是否已上电。")

    def stop(self):
        self.stop_event.set()
        if self.thread and self.thread.is_alive() and threading.current_thread() is not self.thread:
            self.thread.join(timeout=1.5)
        self.thread = None
        self._drain_queue(self.tx_queue)
        self._drain_queue(self.rx_queue)
        self._drain_queue(self.event_queue)

    def send(self, data: bytes):
        if not data:
            return
        try:
            self.tx_queue.put_nowait(bytes(data))
        except queue.Full:
            self.event_queue.put(("error", "BLE 发送队列已满，已丢弃本次数据"))

    def poll_rx(self):
        chunks = []
        while True:
            try:
                chunks.append(self.rx_queue.get_nowait())
            except queue.Empty:
                break
        return chunks

    def poll_events(self):
        items = []
        while True:
            try:
                items.append(self.event_queue.get_nowait())
            except queue.Empty:
                break
        return items

    @staticmethod
    def _drain_queue(q):
        while True:
            try:
                q.get_nowait()
            except queue.Empty:
                return

    def _thread_main(self):
        try:
            asyncio.run(self._runner())
        except Exception as exc:
            self.event_queue.put(("error", str(exc)))

    async def _runner(self):
        while not self.stop_event.is_set():
            try:
                disconnected = asyncio.Event()

                def _on_disconnect(_client):
                    try:
                        disconnected.set()
                    except Exception:
                        pass

                client = BleakClient(self.address, disconnected_callback=_on_disconnect)
                await client.connect(timeout=8.0)
                await client.start_notify(self.notify_uuid, self._on_notify)
                self.first_connected.set()
                self.event_queue.put(("connected", f"BLE {self.address}"))

                while not self.stop_event.is_set() and client.is_connected and not disconnected.is_set():
                    await self._flush_tx(client)
                    await asyncio.sleep(0.01)

                try:
                    if client.is_connected:
                        await client.stop_notify(self.notify_uuid)
                        await client.disconnect()
                except Exception:
                    pass

                if self.stop_event.is_set():
                    break
                self.event_queue.put(("disconnected", "BLE 已断开"))
                if not self.auto_reconnect:
                    break
                self.event_queue.put(("reconnecting", "BLE 已断开，正在自动重连…"))
                await asyncio.sleep(1.0)
            except Exception as exc:
                self.event_queue.put(("error", f"BLE: {exc}"))
                if not self.auto_reconnect or self.stop_event.is_set():
                    break
                self.event_queue.put(("reconnecting", "BLE 连接失败，1 秒后重试…"))
                await asyncio.sleep(1.0)

    def _on_notify(self, _sender, data):
        if data:
            self.rx_queue.put(bytes(data))

    async def _flush_tx(self, client):
        while True:
            try:
                raw = self.tx_queue.get_nowait()
            except queue.Empty:
                return
            # 20 bytes is conservative and works on the default ATT MTU. The protocol
            # parser reassembles the JSON line on the receiver side.
            for i in range(0, len(raw), self.chunk_size):
                chunk = raw[i:i + self.chunk_size]
                try:
                    await client.write_gatt_char(self.write_uuid, chunk, response=False)
                except Exception:
                    # Some GATT characteristics only expose Write With Response.
                    await client.write_gatt_char(self.write_uuid, chunk, response=True)
