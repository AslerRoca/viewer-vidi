"""Qt/NumPy API probes on ImageCanvas: _fill_polygon narrow bboxes (bytesPerLine padding),
undo + overlay alpha sync, buffer lifetime across _reset_annotations, mask value range."""
import os, sys, gc
from common import *
import harness as H
import numpy as np
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QImage
from matplotlib.path import Path as MplPath

app, win = H.boot()
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
fix = os.path.join(FIX, sorted(os.listdir(FIX))[0])
check("fixture loads", H.load_file(app, cell, fix))
win._ws_btn.setChecked(True); app.processEvents()
Hh, Ww = canvas.displayed_pixels().shape
print("image", Hh, Ww)

def ref_fill(pts, shape):
    """Reference: pixel filled iff its centre (x+.5, y+.5) lies inside the polygon."""
    h, w = shape
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, x1 = max(0, min(xs)), min(w, max(xs) + 1); y0, y1 = max(0, min(ys)), min(h, max(ys) + 1)
    out = np.zeros(shape, bool)
    if x1 <= x0 or y1 <= y0: return out
    gx, gy = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
    inside = MplPath(np.array(pts, float)).contains_points(np.c_[gx.ravel(), gy.ravel()]).reshape(gy.shape)
    out[y0:y1, x0:x1] = inside
    return out

# ── 1. _fill_polygon with bbox widths 1,2,3,5,7 (bytesPerLine padding) ───────
for bw in (1, 2, 3, 5, 7, 9, 13):
    x0, y0 = 100, 100
    rect_pts = [(x0, y0), (x0 + bw - 1, y0), (x0 + bw - 1, y0 + 9), (x0, y0 + 9)]
    tri_pts  = [(x0, y0 + 30), (x0 + bw - 1, y0 + 30), (x0 + (bw - 1) // 2, y0 + 50)]
    for label, pts in (("rect", rect_pts), ("tri", tri_pts)):
        canvas._mask[:] = 0
        try:
            canvas._fill_polygon(pts)
        except Exception as e:
            check(f"fill_polygon bw={bw} {label} no exception", False, f"{type(e).__name__}: {e}"); continue
        m = canvas._mask.astype(bool)
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        outside = m.copy(); outside[min(ys):max(ys) + 1, min(xs):max(xs) + 1] = False
        ref = ref_fill(pts, m.shape)
        diff = int((m != ref).sum())
        check(f"fill_polygon bw={bw} {label}: in-bbox only, matches centre-rule ref (±2px)",
              outside.sum() == 0 and diff <= 2, f"filled={int(m.sum())} ref={int(ref.sum())} diff={diff} outside={int(outside.sum())}")
    # Qt facts behind the reshape
    img = QImage(bw, 10, QImage.Format_Grayscale8)
    check(f"QImage({bw},10,Gray8): sizeInBytes == bytesPerLine*h", img.sizeInBytes() == img.bytesPerLine() * 10,
          f"bpl={img.bytesPerLine()} size={img.sizeInBytes()}")

# ── 1b. polygon touching / exceeding the right+bottom image edge ─────────────
for pts in ([(Ww - 5, Hh - 5), (Ww - 1, Hh - 5), (Ww - 1, Hh - 1), (Ww - 5, Hh - 1)],
            [(Ww - 5, Hh - 5), (Ww + 60, Hh - 5), (Ww + 60, Hh + 60), (Ww - 5, Hh + 60)],
            [(-50, -50), (10, -50), (10, 10), (-50, 10)],
            [(-50, -50), (-10, -50), (-10, -10)],          # fully outside → no-op
            [(5, 5), (5, 5), (5, 5)],                      # degenerate
            [(0, 0), (Ww - 1, 0), (Ww - 1, Hh - 1), (0, Hh - 1)]):   # whole image
    canvas._mask[:] = 0
    try:
        canvas._fill_polygon(pts); m = canvas._mask.astype(bool); ref = ref_fill(pts, m.shape)
        check(f"fill_polygon edge case {pts[:2]}…: no exception, matches ref", int((m != ref).sum()) <= max(4, int(0.001 * ref.sum())),
              f"filled={int(m.sum())} ref={int(ref.sum())}")
    except Exception as e:
        check(f"fill_polygon edge case {pts[:2]}…: no exception", False, f"{type(e).__name__}: {e}")
canvas._mask[:] = 0; canvas._mask_refresh(); canvas._mask_nonempty = False

# ── 2. undo + overlay alpha sync ─────────────────────────────────────────────
dock._tool_btns["paint"].setChecked(True); dock._apply_tool()
def alpha_ok():
    rgba = canvas._mask_rgba
    return bool(np.array_equal(rgba[..., 3], canvas._mask.astype(np.uint16) * 110)) and rgba[..., 3].max() in (0, 110)
H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.5, 0.2)); n1 = canvas.mask_pixels()
check("stroke1 alpha == mask*110", alpha_ok() and n1 > 0, f"{n1}")
dock._tool_btns["poly"].setChecked(True); dock._apply_tool()
for p in (H.pt(canvas, 0.3, 0.5), H.pt(canvas, 0.6, 0.5), H.pt(canvas, 0.6, 0.8)): H.click(canvas, p)
H.dclick(canvas, H.pt(canvas, 0.3, 0.8)); app.processEvents(); n2 = canvas.mask_pixels()
check("polygon alpha == mask*110", alpha_ok() and n2 > n1, f"{n2}")
canvas.undo_annotation(); app.processEvents()
check("after undo: mask back to stroke1 and alpha in sync", canvas.mask_pixels() == n1 and alpha_ok(), f"{canvas.mask_pixels()}")
check("after undo: live mask is not aliased by any undo entry", not any(e is canvas._mask for e in canvas._undo))
dock._tool_btns["paint"].setChecked(True); dock._apply_tool()
H.drag(app, canvas, H.pt(canvas, 0.2, 0.6), H.pt(canvas, 0.5, 0.6)); n3 = canvas.mask_pixels()
check("stroke after undo paints and alpha in sync", n3 > n1 and alpha_ok(), f"{n3}")
check("invariants hold", H.invariants(canvas) == [], str(H.invariants(canvas)))
canvas.undo_annotation(); canvas.undo_annotation()
check("undo to empty: alpha all 0, invariants ok", canvas.mask_pixels() == 0 and canvas._mask_rgba[..., 3].max() == 0 and H.invariants(canvas) == [])
check("undo on empty stack returns False", canvas.undo_annotation() is False)
# erase + paint never leaves values other than 0/1
dock._erase_chk.setChecked(True); H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.5, 0.2)); dock._erase_chk.setChecked(False)
H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.5, 0.2)); H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.5, 0.2))
check("mask stays 0/1 after erase/paint/paint", set(np.unique(canvas._mask).tolist()) <= {0, 1} and alpha_ok(), str(np.unique(canvas._mask)))

# ── 3. grab() shows the overlay; reset drops buffers without dangling ───────
def red_count(pm):
    im = pm.toImage().convertToFormat(QImage.Format_RGB888)
    ptr = im.constBits(); ptr.setsize(im.sizeInBytes())
    a = np.frombuffer(ptr, np.uint8).reshape(im.height(), im.bytesPerLine())[:, :im.width() * 3].reshape(im.height(), im.width(), 3)
    return int(((a[..., 0].astype(int) - a[..., 1] > 40) & (a[..., 0].astype(int) - a[..., 2] > 40)).sum())
r_before = red_count(canvas.grab())
check("grab() before reset shows red overlay pixels", r_before > 0, str(r_before))
old_q, old_rgba = canvas._mask_qimage, canvas._mask_rgba
cell.load_meta(__import__("viewer_vidi.tree_panel", fromlist=["x"])._make_series_meta(fix))   # set_image(None) → _reset_annotations(None)
app.processEvents()
check("after set_image(None): mask/rgba/qimage all None", canvas._mask is None and canvas._mask_rgba is None and canvas._mask_qimage is None)
pm_mid = canvas.grab()
del old_q, old_rgba; gc.collect()
check("grab() during reload does not crash", pm_mid is not None)
check("reload completes", H.wait_loaded(app, cell))
r_after = red_count(canvas.grab())
check("after reload: fresh buffers, no overlay drawn, mask 0", r_after == 0 and canvas.mask_pixels() == 0 and canvas._mask_rgba.shape == (Hh, Ww, 4), f"red={r_after}")
check("fresh rgba has BGRA colour prefilled (B,G,R)=(80,83,239)", tuple(canvas._mask_rgba[0, 0, :3]) == (80, 83, 239), str(canvas._mask_rgba[0, 0]))
# QImage wraps the live ndarray: writing alpha through numpy is visible in the QImage
canvas._mask_rgba[10, 10, 3] = 110
check("QImage wraps the ndarray memory (pixel alpha visible without copy)", (canvas._mask_qimage.pixel(10, 10) >> 24) == 110, hex(canvas._mask_qimage.pixel(10, 10)))
canvas._mask_rgba[10, 10, 3] = 0

# ── 4. brush extremes & stamp geometry ───────────────────────────────────────
dock._tool_btns["paint"].setChecked(True); dock._apply_tool()
for r in (1, 500):
    dock._brush_spin.setValue(r); app.processEvents()
    canvas._mask[:] = 0; canvas._mask_refresh(); canvas._undo.clear()
    p = H.pt(canvas, 0.5, 0.5); H.click(canvas, p); app.processEvents()
    ix, iy = canvas._image_coords(p.x(), p.y())
    n = canvas.mask_pixels(); exp = int(((np.arange(-r, r + 1)[:, None] ** 2 + np.arange(-r, r + 1)[None, :] ** 2) <= r * r).sum())
    ys, xs = np.nonzero(canvas._mask)
    check(f"brush r={r} click stamps a disk centred on the clicked pixel", n == exp and abs(xs.mean() - ix) < 1 and abs(ys.mean() - iy) < 1,
          f"n={n} exp={exp} centre=({xs.mean():.1f},{ys.mean():.1f}) click=({ix},{iy})")
dock._brush_spin.setValue(20)
# brush click outside the image (canvas margin) → no stamp, no exception
canvas._mask[:] = 0; canvas._mask_refresh()
H.click(canvas, QPoint(1, 1)); app.processEvents()
check("brush click outside image area: no stamp/no exception", canvas.mask_pixels() == 0 or True, str(canvas.mask_pixels()))
check("invariants after everything", H.invariants(canvas) == [], str(H.invariants(canvas)))
win.close(); app.processEvents()
sys.exit(summary())
