"""Live default-output-device lookup via CoreAudio.

PortAudio (sounddevice) snapshots the device list when it initializes, so it
keeps reporting whatever the default output was at backend start. macOS can
switch outputs at any moment (earbuds connect, the user changes it) — and if
sound stops flowing through the Recording Output device, the client's side
of a call is silently lost. This asks the CoreAudio HAL directly on every
call, so the answer is always current, even while recording streams are open.
"""

from __future__ import annotations

import ctypes
import ctypes.util


def _fourcc(code: str) -> int:
    return int.from_bytes(code.encode(), "big")


class _PropertyAddress(ctypes.Structure):
    _fields_ = [
        ("mSelector", ctypes.c_uint32),
        ("mScope", ctypes.c_uint32),
        ("mElement", ctypes.c_uint32),
    ]


_SYSTEM_OBJECT = 1
_SELECTOR_DEFAULT_OUTPUT = _fourcc("dOut")
_SELECTOR_NAME = _fourcc("lnam")
_SCOPE_GLOBAL = _fourcc("glob")
_UTF8 = 0x08000100

try:
    _ca = ctypes.CDLL(ctypes.util.find_library("CoreAudio"))
    _cf = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))
    _cf.CFStringGetCString.restype = ctypes.c_bool
except Exception:  # not on macOS / library unavailable
    _ca = None
    _cf = None


def default_output_name() -> str | None:
    """Name of the current system default output device, or None if unknown."""
    if _ca is None or _cf is None:
        return None
    try:
        addr = _PropertyAddress(_SELECTOR_DEFAULT_OUTPUT, _SCOPE_GLOBAL, 0)
        device = ctypes.c_uint32(0)
        size = ctypes.c_uint32(ctypes.sizeof(device))
        err = _ca.AudioObjectGetPropertyData(
            _SYSTEM_OBJECT, ctypes.byref(addr), 0, None,
            ctypes.byref(size), ctypes.byref(device),
        )
        if err or not device.value:
            return None

        addr = _PropertyAddress(_SELECTOR_NAME, _SCOPE_GLOBAL, 0)
        cfstr = ctypes.c_void_p(0)
        size = ctypes.c_uint32(ctypes.sizeof(cfstr))
        err = _ca.AudioObjectGetPropertyData(
            device.value, ctypes.byref(addr), 0, None,
            ctypes.byref(size), ctypes.byref(cfstr),
        )
        if err or not cfstr.value:
            return None

        buf = ctypes.create_string_buffer(256)
        ok = _cf.CFStringGetCString(cfstr, buf, 256, _UTF8)
        _cf.CFRelease(cfstr)
        return buf.value.decode("utf-8", errors="replace") if ok else None
    except Exception:
        return None
