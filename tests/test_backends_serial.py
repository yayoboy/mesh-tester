# tests/test_backends_serial.py
from src.backends.serial import SerialBackend


class FakeIface:
    def __init__(self, port):
        self.port = port
        self.sent = []
    def getMyNodeInfo(self):
        return {"num": 2712847316, "user": {"id": "!a1b2c3d4", "longName": "Real One"}}
    def sendText(self, text, destinationId="^all", channelIndex=0, **kw):
        self.sent.append(("text", text, destinationId, channelIndex))
    def sendPosition(self, **kw):
        self.sent.append(("position",))
    def sendTelemetry(self, **kw):
        self.sent.append(("telemetry",))
    def close(self):
        self.closed = True


def _backend():
    events = []
    b = SerialBackend("/dev/ttyUSB0", sink=events.append,
                      interface_factory=lambda port: FakeIface(port))
    return b, events


def test_connect_reads_node_identity():
    b, _ = _backend()
    assert b.connected is False
    b.connect()
    assert b.connected is True
    assert b.id == "!a1b2c3d4" and b.longname == "Real One" and b.kind == "serial"


def test_send_text_calls_iface():
    b, _ = _backend()
    b.connect()
    b.send_text("hello", to="!ffffffff", channel=2)
    assert b._iface.sent == [("text", "hello", "!ffffffff", 2)]


def test_rx_callback_emits_event():
    b, events = _backend()
    b.connect()
    packet = {"fromId": "!deadbeef", "rxSnr": 6.25, "rxRssi": -88, "hopLimit": 3,
              "channel": 0, "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "ping"}}
    b._on_receive(packet=packet, interface=b._iface)
    assert len(events) == 1
    ev = events[0]
    assert ev.from_id == "!deadbeef" and ev.snr == 6.25 and ev.payload == "ping"
    assert ev.ptype == "TEXT_MESSAGE_APP"


def test_disconnect_closes_iface():
    b, _ = _backend()
    b.connect()
    b.disconnect()
    assert b.connected is False and getattr(b._iface, "closed", False) is True
