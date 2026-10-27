"""Tiny helpers shared by the perf-lens scripts."""
import time, json

def rss_mb():
    with open("/proc/self/status") as f:
        for ln in f:
            if ln.startswith("VmRSS"):
                return int(ln.split()[1]) / 1024.0
    return -1.0

class T:
    """with T() as t: ...; t.ms"""
    def __enter__(self):
        self.t0 = time.perf_counter(); return self
    def __exit__(self, *a):
        self.ms = (time.perf_counter() - self.t0) * 1000.0

def ms(fn, *a, **k):
    t0 = time.perf_counter(); out = fn(*a, **k); return (time.perf_counter() - t0) * 1000.0, out

def pump_until_painted(app, canvas, timeout=5.0):
    """processEvents until a paintEvent has run (canvas._paint_count bumped)."""
    before = getattr(canvas, "_perf_paints", 0)
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < timeout:
        app.processEvents()
        if getattr(canvas, "_perf_paints", 0) > before:
            return True
    return False

def instrument_paint(canvas):
    """Count paintEvents on this canvas (monkeypatch on the instance)."""
    import types
    orig = type(canvas).paintEvent
    canvas._perf_paints = 0
    canvas._perf_paint_ms = []
    def pe(self, ev):
        t0 = time.perf_counter(); orig(self, ev)
        self._perf_paint_ms.append((time.perf_counter() - t0) * 1000.0); self._perf_paints += 1
    canvas.paintEvent = types.MethodType(pe, canvas)
