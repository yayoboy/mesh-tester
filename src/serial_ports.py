from __future__ import annotations


def _find_meshtastic_ports() -> list[str]:
    from meshtastic.util import findPorts
    return list(findPorts())


def _find_pyserial_ports() -> list[str]:
    from serial.tools import list_ports as _lp
    return [p.device for p in _lp.comports()]


def list_ports() -> list[str]:
    """Candidate serial device paths for Meshtastic devices. Never raises."""
    try:
        ports = _find_meshtastic_ports()
        if ports:
            return ports
    except Exception:
        pass
    try:
        return _find_pyserial_ports()
    except Exception:
        return []
