"""Perf lens (Qt offscreen): (1) residual RSS after an 8192² item is replaced by a small one — attribute to
feature buffers vs the preexisting cupy pinned/device pools; (2) polygon with 2000 vertices at 8192²."""
import os, sys, time, json, gc, math
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB); sys.path.insert(0, STAB + "/perf")
import harness as H
from perfutil import rss_mb, ms, instrument_paint
from PyQt5.QtCore import Qt, QPoint
BIG = os.path.join(STAB, "perf", "fix", "big", "png8192_8.png")
SMALL = "/media/zsk/ressd/research/alldata_backup/project_workstation/PhD/image_exsample/3.png"
app, win = H.boot()
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas(); instrument_paint(canvas)
win._ws_btn.setChecked(True); app.processEvents()
R = {}
r_boot = rss_mb()
H.load_file(app, cell, SMALL); dock._apply_tool(); app.processEvents()
r_small0 = rss_mb()
H.load_file(app, cell, BIG); dock._apply_tool(); app.processEvents()
r_big = rss_mb()
# a few strokes so undo snapshots + overlay alpha exist
for i in range(5):
    a = H.pt(canvas, 0.1 + 0.1 * i, 0.5); H.drag(app, canvas, a, QPoint(a.x() + 60, a.y()), steps=4)
r_big_strokes = rss_mb()
# polygon with 2000 vertices (circle), hover-move repaint cost with the rubber band + vertex squares
dock._tool_btns["poly"].setChecked(True); dock._apply_tool(); app.processEvents()
for k in range(2000):
    H.click(canvas, H.pt(canvas, 0.5 + 0.45 * math.cos(2 * math.pi * k / 2000), 0.5 + 0.45 * math.sin(2 * math.pi * k / 2000)))
R["poly_vertices"] = len(canvas._poly_pts)
dts = []
for i in range(20):
    t0 = time.perf_counter(); H.move(canvas, H.pt(canvas, 0.3 + 0.01 * i, 0.3)); app.processEvents(); dts.append((time.perf_counter() - t0) * 1000)
R["poly2000_hover_move_plus_repaint_ms"] = dict(mean=round(sum(dts) / len(dts), 1), max=round(max(dts), 1))
canvas.setFocus(); t0 = time.perf_counter(); H.key(canvas, Qt.Key_Return); R["poly2000_fill_ms"] = round((time.perf_counter() - t0) * 1000, 1)
app.processEvents(); R["poly2000_mask_px"] = canvas.mask_pixels()
# replace by the small item
H.load_file(app, cell, SMALL); dock._apply_tool(); app.processEvents(); gc.collect()
r_small1 = rss_mb()
import cupy
pin = cupy.get_default_pinned_memory_pool(); dev = cupy.get_default_memory_pool()
R["cupy_pinned_free_blocks_before"] = pin.n_free_blocks()
R["cupy_device_pool_MB"] = dict(used=round(dev.used_bytes() / 2**20), total=round(dev.total_bytes() / 2**20))
pin.free_all_blocks(); gc.collect(); r_after_pin = rss_mb()
dev.free_all_blocks(); r_after_dev = rss_mb()
R["rss_MB"] = dict(boot=round(r_boot), small_first=round(r_small0), big_loaded=round(r_big), big_plus_5_strokes=round(r_big_strokes),
                   small_again=round(r_small1), after_cupy_pinned_free=round(r_after_pin), after_cupy_device_free=round(r_after_dev))
R["canvas_after_small"] = dict(mask_shape=list(canvas.mask().shape), rgba_shape=list(canvas._mask_rgba.shape), undo=len(canvas._undo),
                               vol_MB=round(cell._vol.nbytes / 2**20, 2), rgb_MB=round(canvas._rgb_buf.nbytes / 2**20, 2))
R["residual_vs_first_small_MB"] = round(r_small1 - r_small0)
R["residual_after_cupy_pools_freed_MB"] = round(r_after_dev - r_small0)
win.close(); app.processEvents()
print(json.dumps(R, indent=1))
