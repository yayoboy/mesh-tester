import pytest
from src.backends.base import NodeBackend, RxEvent


def test_rxevent_holds_signal_fields():
    ev = RxEvent(backend_id="!aa", from_id="!bb", ptype="text", payload="hi",
                 snr=5.5, rssi=-90, hops=3, channel=0, ts=1.0)
    assert ev.from_id == "!bb" and ev.snr == 5.5 and ev.payload == "hi"


def test_nodebackend_is_abstract():
    with pytest.raises(TypeError):
        NodeBackend()  # cannot instantiate the ABC directly
