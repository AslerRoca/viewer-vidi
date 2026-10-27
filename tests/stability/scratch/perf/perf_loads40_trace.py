"""Perf lens (Qt offscreen): 40 sequential item loads (alternating fixtures) -> RSS trend, tracemalloc, buffer release."""
import os, sys, time, json, gc, tracemalloc, shutil
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB); sys.path.insert(0, STAB + "/perf")
import harness as H
from perfutil import rss_mb, ms
import numpy as np
from PyQt5.QtCore import Qt, QPoint

WS = os.path.join(STAB, "perf", "ws", "loads40"); shutil.rmtree(WS, ignore_errors=True); os.makedirs(WS)
lst = os.path.join(WS, "list40.txt"); shutil.copy(os.path.join(STAB, "perf", "fix", "list40.txt"), lst)
app, win = H.boot()
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
R = {}
tracemalloc.start(10)
r0 = rss_mb()
t0 = time.perf_counter()
ws = H.open_workspace(app, win, WS, mode="list", list_file=lst, out_dir="out")
R["n_items"] = len(ws.items); R["first_load_s"] = round(time.perf_counter() - t0, 2)
rows = []
snap_a = tracemalloc.take_snapshot()
def one_stroke():
    a = H.pt(canvas, 0.3, 0.5); H.drag(app, canvas, a, QPoint(a.x() + 80, a.y()), steps=4)
one_stroke()
rows.append(dict(i=0, item=os.path.basename(ws.items[0].path), shape=list(canvas.displayed_pixels().shape),
                 rss_MB=round(rss_mb()), undo=len(canvas._undo), mask_px=canvas.mask_pixels()))
for i in range(1, len(ws.items)):
    t0 = time.perf_counter(); dock._step(+1); ok = H.wait_loaded(app, cell, timeout=60); dt = time.perf_counter() - t0
    if not ok:
        rows.append(dict(i=i, item=os.path.basename(ws.items[i].path), FAILED_TO_LOAD=True)); continue
    undo_before = len(canvas._undo); mp_before = canvas.mask_pixels(); crop_before = canvas.crop_rect()
    one_stroke()
    rows.append(dict(i=i, item=os.path.basename(ws.items[i].path), shape=list(canvas.displayed_pixels().shape),
                     load_s=round(dt, 2), rss_MB=round(rss_mb()), undo_before_stroke=undo_before,
                     mask_px_before_stroke=mp_before, crop_before=crop_before, mask_px=canvas.mask_pixels(),
                     mode=canvas.wl_mode()))
gc.collect(); app.processEvents()
snap_b = tracemalloc.take_snapshot()
R["rss_start_MB"] = round(r0); R["rss_end_MB"] = round(rss_mb())
R["rows"] = rows[-3:]
same_pos = [r["rss_MB"] for r in rows if r.get("rss_MB") is not None and r["i"] % 8 == 7]
R["rss_at_cycle_end_MB (items 7,15,23,31,39)"] = same_pos
top = snap_b.compare_to(snap_a, "lineno")[:12]
R["tracemalloc_top_growth"] = ["\n".join([f"{s.size_diff/2**20:+.1f} MB ({s.count_diff:+d} blocks)"] + s.traceback.format()[-8:]) for s in top[:6]]
cur, peak = tracemalloc.get_traced_memory(); R["tracemalloc_current_MB"] = round(cur / 2**20); R["tracemalloc_peak_MB"] = round(peak / 2**20)
big = [(list(a.shape), str(a.dtype), round(a.nbytes / 2**20)) for a in gc.get_objects() if isinstance(a, np.ndarray) and a.nbytes >= 8 * 2**20]
R["live_arrays_ge_8MB_at_end"] = big
R["bad"] = [r for r in rows if r.get("FAILED_TO_LOAD") or r.get("undo_before_stroke") or r.get("mask_px_before_stroke") or r.get("crop_before") is not None or r.get("mode") != "paint"]
win.close(); app.processEvents()
print(json.dumps(R, indent=1))
