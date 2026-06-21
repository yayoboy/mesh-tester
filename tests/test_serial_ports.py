import src.serial_ports as sp


def test_list_ports_uses_meshtastic_findports(monkeypatch):
    monkeypatch.setattr(sp, "_find_meshtastic_ports", lambda: ["/dev/ttyUSB0", "/dev/ttyUSB1"])
    assert sp.list_ports() == ["/dev/ttyUSB0", "/dev/ttyUSB1"]


def test_list_ports_never_raises(monkeypatch):
    def boom():
        raise RuntimeError("no lib")
    monkeypatch.setattr(sp, "_find_meshtastic_ports", boom)
    monkeypatch.setattr(sp, "_find_pyserial_ports", lambda: [])
    assert sp.list_ports() == []
