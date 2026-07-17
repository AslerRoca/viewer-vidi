"""Direct kernel reader for mouse tilt-wheel (horizontal scroll) events.

Qt 5.15's X11 backend loses isolated horizontal scroll detents: its
scroll-valuator bookkeeping goes stale during idle, so the first tilt
click after a pause (or a direction change) is silently swallowed and
only flushed once further clicks arrive. The kernel, libinput, and the
X server all deliver every detent (verified with evdev/xev probes) —
the loss is inside Qt, and no Qt-side setting recovers it.

This module bypasses Qt on Linux by reading REL_HWHEEL events straight
from /dev/input/event*. Requires read access to those devices (user in
the ``input`` group). When unavailable, the caller keeps the plain Qt
wheel path as fallback.
"""
from __future__ import annotations

import os
import select
import struct
import sys
import threading
import time

from PyQt5.QtCore import QObject, pyqtSignal

_EVENT_FMT  = "llHHi"                    # struct input_event (64-bit)
_EVENT_SIZE = struct.calcsize(_EVENT_FMT)
_EV_REL     = 0x02
_REL_HWHEEL = 0x06
_RESCAN_S   = 3.0                        # hotplug poll (receiver reconnects)


def find_tilt_devices() -> list[str]:
    """Event devices advertising a horizontal wheel (REL_HWHEEL bit)."""
    paths: list[str] = []
    try:
        with open("/proc/bus/input/devices") as f:
            blocks = f.read().split("\n\n")
    except OSError:
        return paths
    for block in blocks:
        event, rel = None, 0
        for line in block.splitlines():
            if line.startswith("H: Handlers="):
                for tok in line.split():
                    if tok.startswith("event"):
                        event = tok
            elif line.startswith("B: REL="):
                rel = int(line.split("=", 1)[1].split()[0], 16)
        if event and rel >> _REL_HWHEEL & 1:
            paths.append(f"/dev/input/{event}")
    return paths


class TiltWheelReader(QObject):
    """Emits tilt_stepped(steps) per detent: +1 tilt right, -1 tilt left."""

    tilt_stepped = pyqtSignal(int)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._fds: dict[int, str] = {}   # fd -> path

    def start(self) -> bool:
        """Open tilt devices; spawn the reader thread. False if none readable."""
        if not sys.platform.startswith("linux"):
            return False
        candidates = find_tilt_devices()
        self._open_new(candidates)
        if not self._fds:
            if candidates:
                print("viewer-vidi: tilt-wheel device found but not readable; "
                      "for single-click time scrubbing run: "
                      "sudo usermod -aG input $USER  (then log out/in)",
                      file=sys.stderr)
            return False
        threading.Thread(target=self._run, daemon=True,
                         name="tilt-evdev").start()
        return True

    def _open_new(self, paths: list[str]) -> None:
        known = set(self._fds.values())
        for path in paths:
            if path in known:
                continue
            try:
                self._fds[os.open(path, os.O_RDONLY | os.O_NONBLOCK)] = path
            except OSError:
                pass

    def _close(self, fd: int) -> None:
        self._fds.pop(fd, None)
        try:
            os.close(fd)
        except OSError:
            pass

    def _run(self) -> None:
        next_rescan = time.monotonic() + _RESCAN_S
        while True:
            fds = list(self._fds)
            r, _, _ = select.select(fds, [], [], 1.0) if fds else ([], [], [])
            if not fds:
                time.sleep(1.0)
            for fd in r:
                try:
                    data = os.read(fd, _EVENT_SIZE * 64)
                except OSError:
                    self._close(fd)
                    continue
                for off in range(0, len(data) - _EVENT_SIZE + 1, _EVENT_SIZE):
                    _, _, etype, code, value = struct.unpack_from(
                        _EVENT_FMT, data, off)
                    if etype == _EV_REL and code == _REL_HWHEEL and value:
                        self.tilt_stepped.emit(value)
            if time.monotonic() >= next_rescan:
                next_rescan = time.monotonic() + _RESCAN_S
                self._open_new(find_tilt_devices())
