"""Shared helpers for the canvasgeom lens."""
import os, sys, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
import numpy as np

RESULTS = []
def check(name, cond, info=""):
    ok = bool(cond)
    RESULTS.append((name, ok, info))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{info}]" if info else ""), flush=True)
    return ok

def inv(canvas, label):
    bad = H.invariants(canvas)
    return check(f"invariants after {label}", not bad, "; ".join(bad))

def centroid(mask):
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return (float(xs.mean()), float(ys.mean()))

def bbox(mask):
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))

def summary():
    n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
    print(f"\n{len(RESULTS) - n_fail}/{len(RESULTS)} checks passed", flush=True)
    return n_fail

def tool(dock, mode):
    dock._tool_btns[mode].setChecked(True); dock._apply_tool()

def wpt(canvas, x, y):
    """Absolute widget point."""
    from PyQt5.QtCore import QPoint
    return QPoint(int(x), int(y))
