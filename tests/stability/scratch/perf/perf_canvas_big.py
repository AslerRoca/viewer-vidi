"""Perf lens (Qt offscreen): one big PNG as a workspace item.
usage: python perf_canvas_big.py <png> <label>
Measures load, repaint (with/without overlay), brush per-MouseMove, whole-image polygon fill,
_refresh_stats cost, undo-stack RSS, GUI-thread block of Save, release on next item, set_image(None)."""
import os, sys, time, json, gc
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB); sys.path.insert(0, STAB + "/perf")
import harness as H
from perfutil import rss_mb, ms, instrument_paint
import numpy as np

img, label = sys.argv[1], sys.argv[2]
SMALL = "/media/zsk/ressd/research/alldata_backup/project_workstation/PhD/image_exsample/3.png"
WS = os.path.join(STAB, "perf", "ws", label)
import shutil; shutil.rmtree(WS, ignore_errors=True); os.makedirs(WS)
lst = os.path.join(WS, "items.txt")
open(lst, "w").write(img + "\n" + SMALL + "\n")

from PyQt5.QtCore import Qt, QTimer, QPoint
app, win = H.boot()
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
instrument_paint(canvas)
ticks = [0]
tm = QTimer(); tm.setInterval(20); tm.timeout.connect(lambda: ticks.__setitem__(0, ticks[0] + 1)); tm.start()
R = {"label": label, "file": os.path.basename(img), "file_MB": round(os.path.getsize(img) / 1e6, 1)}
def nb(a): return round(a.nbytes / 2**20) if a is not None else None

r0 = rss_mb()
t0 = time.perf_counter()
ws = H.open_workspace(app, win, WS, mode="list", list_file=lst, out_dir="out")
R["load_s"] = round(time.perf_counter() - t0, 2)
px = canvas.displayed_pixels()
R["shape"] = list(px.shape); R["pixels_dtype"] = str(px.dtype)
R["rss_after_load_delta_MB"] = round(rss_mb() - r0)
R["buffers_MB"] = dict(pixels=nb(px), vol=nb(cell._vol), vol_shares_pixels=bool(np.shares_memory(cell._vol, px)),
                       rgb_buf=nb(canvas._rgb_buf), mask=nb(canvas.mask()), mask_rgba=nb(canvas._mask_rgba))
R["mode_after_open"] = canvas.wl_mode()
assert canvas.wl_mode() == "paint", canvas.wl_mode()

def repaint_stats(n=20):
    canvas._perf_paint_ms.clear()
    for _ in range(n): canvas.repaint()
    v = canvas._perf_paint_ms[:]
    return dict(n=len(v), mean_ms=round(sum(v) / len(v), 1), max_ms=round(max(v), 1))
R["repaint_no_overlay"] = repaint_stats()

# hover (no button) in paint mode: every move calls update() -> repaint
pts = [H.pt(canvas, 0.2 + 0.01 * i, 0.5) for i in range(20)]
dts = []
for p in pts:
    t0 = time.perf_counter(); H.move(canvas, p); app.processEvents(); dts.append((time.perf_counter() - t0) * 1000)
R["hover_move_plus_repaint_ms_mean"] = round(sum(dts) / len(dts), 1)

def stroke(radius, steps, fx0=0.1, fx1=None, fy=0.5):
    """500-screen-px horizontal drag; returns per-move ms list, full-stroke ms, repaint ms."""
    dock._brush_spin.setValue(radius); app.processEvents()
    a = H.pt(canvas, fx0, fy); b = QPoint(a.x() + 500, a.y())
    canvas._perf_paint_ms.clear()
    t_all = time.perf_counter()
    H.press(canvas, a)
    per = []
    for i in range(1, steps + 1):
        p = QPoint(a.x() + 500 * i // steps, a.y())
        t0 = time.perf_counter(); H.move(canvas, p, Qt.LeftButton); per.append((time.perf_counter() - t0) * 1000)
    H.release(canvas, b)
    app.processEvents()
    full = (time.perf_counter() - t_all) * 1000
    return dict(radius=radius, steps=steps, move_ms_mean=round(sum(per) / len(per), 2), move_ms_max=round(max(per), 2),
                full_stroke_ms=round(full, 1), repaint_ms=round(sum(canvas._perf_paint_ms), 1), mask_px=canvas.mask_pixels())
R["brush_r20_25steps"] = stroke(20, 25)
R["brush_r500_10steps"] = stroke(500, 10, fy=0.3)
R["brush_r500_1step_flick"] = stroke(500, 1, fy=0.7)
R["undo_depth_now"] = len(canvas._undo)
t = [ms(dock._refresh_stats)[0] for _ in range(5)]
R["refresh_stats_ms_mean"] = round(sum(t) / 5, 1)
R["repaint_with_overlay"] = repaint_stats()
R["undo_ms"] = round(ms(canvas.undo_annotation)[0], 1)
R["clear_ms"] = round(ms(canvas.clear_annotations)[0], 1)

# polygon covering the whole image
dock._tool_btns["poly"].setChecked(True); dock._apply_tool(); app.processEvents()
canvas._undo.clear()
for fx, fy in ((0.0005, 0.0005), (0.9995, 0.0005), (0.9995, 0.9995), (0.0005, 0.9995)):
    H.click(canvas, H.pt(canvas, fx, fy))
canvas.setFocus(); app.processEvents()
t0 = time.perf_counter(); H.key(canvas, Qt.Key_Return); t_fill = (time.perf_counter() - t0) * 1000
app.processEvents()
hgt, wid = px.shape
R["polygon_full_image"] = dict(fill_ms=round(t_fill, 1), mask_px=canvas.mask_pixels(), image_px=hgt * wid,
                               coverage=round(canvas.mask_pixels() / (hgt * wid), 4), undo_depth=len(canvas._undo))
R["repaint_with_full_overlay"] = repaint_stats()
R["rss_after_polygon_MB_delta"] = round(rss_mb() - r0)

# undo stack: 11 short strokes -> 10 snapshots expected
dock._tool_btns["paint"].setChecked(True); dock._apply_tool(); dock._brush_spin.setValue(20); app.processEvents()
canvas._undo.clear(); gc.collect()
r1 = rss_mb()
for i in range(11):
    a = H.pt(canvas, 0.1 + 0.05 * i, 0.2); H.drag(app, canvas, a, QPoint(a.x() + 30, a.y()), steps=3)
R["undo_stack"] = dict(depth=len(canvas._undo), snapshots_MB=round(sum(a.nbytes for a in canvas._undo) / 2**20),
                       rss_delta_MB=round(rss_mb() - r1), expected_MB=round(10 * canvas.mask().nbytes / 2**20))
# Save on the GUI thread, all formats + Original (+ mask + crop? no rect) -> measure block
for chk in dock._fmt_chk.values(): chk.setChecked(True)
dock._image_chk.setChecked(True)
app.processEvents(); ticks[0] = 0
import threading
peak = [rss_mb()]; stop = [False]
def _watch():
    while not stop[0]:
        peak[0] = max(peak[0], rss_mb()); time.sleep(0.005)
rs0 = rss_mb(); threading.Thread(target=_watch, daemon=True).start()
t0 = time.perf_counter(); dock._save(advance=False); t_save = time.perf_counter() - t0
stop[0] = True; tk = ticks[0]; app.processEvents()
outd = os.path.join(WS, "out")
files = {os.path.relpath(os.path.join(dp, f), outd): round(os.path.getsize(os.path.join(dp, f)) / 1e6, 1)
         for dp, _, fs in os.walk(outd) for f in fs}
R["save_all3_formats"] = dict(gui_block_s=round(t_save, 2), timer_ticks_during_save=tk, status=dock._status_lbl.text(),
                              n_files=len(files), files_MB=files, peak_rss_delta_during_save_MB=round(peak[0] - rs0))
R["rss_after_save_delta_MB"] = round(rss_mb() - r0)

# next item (small PNG): undo stack + big buffers released?
t0 = time.perf_counter(); dock._step(+1); ok = H.wait_loaded(app, cell); t_next = time.perf_counter() - t0
gc.collect(); app.processEvents()
R["next_item"] = dict(loaded=ok, load_s=round(t_next, 2), shape=list(canvas.displayed_pixels().shape),
                      undo_depth=len(canvas._undo), mask_MB=nb(canvas.mask()), rgba_MB=nb(canvas._mask_rgba),
                      rss_delta_from_start_MB=round(rss_mb() - r0))
big_live = [a.shape for a in gc.get_objects() if isinstance(a, np.ndarray) and a.nbytes >= 32 * 2**20]
R["live_arrays_ge_32MB_after_next"] = [list(s) for s in big_live]

# set_image(None) drops everything?
canvas.set_image(None)
R["set_image_none"] = dict(mask=canvas._mask is None, rgba=canvas._mask_rgba is None, qimage=canvas._mask_qimage is None,
                           gpu=canvas._pixels_gpu is None, undo=len(canvas._undo), crop=canvas.crop_rect())
win.close(); app.processEvents()
print(json.dumps(R, indent=1))
