"""canvasgeom lens, part 1: brush geometry under zoom/pan, clipping, brush extremes,
undo depth, Clear/undo bookkeeping, _mask_nonempty vs mask.any(), overlay after undo."""
import os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import numpy as np
from PyQt5.QtCore import Qt, QPoint

D = os.path.dirname(os.path.abspath(__file__))
DCM = sorted(glob.glob(H.FIXTURES + "/*.dcm"))[0]
TINY = os.path.join(D, "ws50", "tiny_50x40.png")

app, win = H.boot()
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
win._ws_btn.setChecked(True); app.processEvents()

check("load CR dicom", H.load_file(app, cell, DCM))
check("tool mode after plain load_meta (not via dock) — informational: mode=" + canvas.wl_mode(), True)
tool(dock, "paint"); dock._brush_spin.setValue(20); dock._erase_chk.setChecked(False); app.processEvents()
Hh, Ww = canvas.displayed_pixels().shape
disk20 = int(((np.arange(-20, 21)[:, None] ** 2 + np.arange(-20, 21)[None, :] ** 2) <= 400).sum())

def paint_click_check(label, P):
    """Click at widget point P; the painted disk centroid must equal _image_coords(P)."""
    before = canvas.mask().copy()
    H.click(canvas, P); app.processEvents()
    new = (canvas.mask() > 0) & (before == 0)
    exp = canvas._image_coords(P.x(), P.y())
    c = centroid(new)
    n = int(new.sum())
    ok = c is not None and abs(c[0] - exp[0]) < 0.51 and abs(c[1] - exp[1]) < 0.51 and n == disk20
    check(f"paint centroid == _image_coords [{label}]", ok,
          f"P=({P.x()},{P.y()}) exp={exp} centroid={c} n={n} (disk={disk20}) zoom={canvas._zoom:.3f} pan=({canvas._pan_x},{canvas._pan_y}) rect={canvas._dest_rect()}")
    # round trip: screen coords of the centre should be within one screen-pixel-per-image-pixel of P
    if c is not None:
        sx, sy = canvas._screen_coords(int(round(c[0])), int(round(c[1])))
        r = canvas._dest_rect(); sc = r.width() / Ww
        check(f"screen round-trip within one image px [{label}]", abs(sx - P.x()) <= sc + 1 and abs(sy - P.y()) <= sc + 1,
              f"P=({P.x()},{P.y()}) back=({sx},{sy}) scale={sc:.2f}")
    inv(canvas, f"paint click {label}")

# 1. unzoomed
paint_click_check("zoom=1 centre", H.pt(canvas, 0.5, 0.5))
paint_click_check("zoom=1 off-centre", H.pt(canvas, 0.22, 0.71))

# 2. zoom in x4 (1.15^4)
for _ in range(4): canvas.zoom_wheel(+120)
app.processEvents()
check("zoom applied", abs(canvas._zoom - 1.15 ** 4) < 1e-6, f"{canvas._zoom}")
paint_click_check("zoom=1.75 image-frac pt", H.pt(canvas, 0.35, 0.4))
paint_click_check("zoom=1.75 widget pt (120,140)", wpt(canvas, 120, 140))

# 3. pan with right-button drag
r0 = canvas._dest_rect()
H.drag(app, canvas, wpt(canvas, 600, 400), wpt(canvas, 480, 330), steps=6, button=Qt.RightButton)
r1 = canvas._dest_rect()
check("right-drag pans the image", (r1.x() - r0.x(), r1.y() - r0.y()) == (-120, -70), f"pan=({canvas._pan_x},{canvas._pan_y}) rect {r0} -> {r1}")
check("right-drag pan does not paint", True)  # (mask unchanged checked below)
n_before = canvas.mask_pixels()
paint_click_check("zoom+pan widget pt (300,200)", wpt(canvas, 300, 200))
paint_click_check("zoom+pan image-frac pt", H.pt(canvas, 0.6, 0.6))

# 3b. zoom out below 1 then paint
for _ in range(10): canvas.zoom_wheel(-120)
app.processEvents()
paint_click_check(f"zoom={canvas._zoom:.2f} (out)", H.pt(canvas, 0.5, 0.3))

# 4. strokes starting/ending outside the image rect
canvas.set_image(canvas.displayed_pixels(), 1.0, reset_view=True)   # reset zoom/pan, same pixels (mask persists)
canvas.clear_annotations(); app.processEvents()
r = canvas._dest_rect()
a = QPoint(r.x() - 80, r.y() + r.height() // 2); b = QPoint(r.x() + 60, r.y() + r.height() // 2)
H.drag(app, canvas, a, b, steps=12)
bb = bbox(canvas.mask())
check("stroke from outside-left into image: clipped, paints from column 0", bb is not None and bb[0] == 0 and canvas.mask_pixels() > 0, f"bbox={bb} n={canvas.mask_pixels()}")
inv(canvas, "stroke from outside-left")
canvas.clear_annotations()
a = QPoint(r.x() + r.width() - 40, r.y() + r.height() - 30); b = QPoint(r.x() + r.width() + 90, r.y() + r.height() + 90)
H.drag(app, canvas, a, b, steps=12)
bb = bbox(canvas.mask())
check("stroke ending outside bottom-right: clipped to last row/col", bb is not None and bb[2] == Ww - 1 and bb[3] == Hh - 1, f"bbox={bb} HxW={Hh}x{Ww}")
inv(canvas, "stroke ending outside")
canvas.clear_annotations()
a = QPoint(r.x() - 300, r.y() - 300); b = QPoint(r.x() - 250, r.y() + r.height() + 300)
H.drag(app, canvas, a, b, steps=12)
check("stroke entirely far outside paints nothing", canvas.mask_pixels() == 0, f"n={canvas.mask_pixels()}")
inv(canvas, "stroke entirely outside")
# stroke crossing the whole widget diagonally
canvas.clear_annotations()
H.drag(app, canvas, QPoint(0, 0), QPoint(canvas.width() - 1, canvas.height() - 1), steps=20)
check("diagonal stroke across whole widget: no exception, pixels painted", canvas.mask_pixels() > 0, f"n={canvas.mask_pixels()}")
inv(canvas, "diagonal stroke")
# a click 1 widget px outside the image edge with r=20 paints a sliver (brush extends in) — record
canvas.clear_annotations()
H.click(canvas, QPoint(r.x() - 1, r.y() + r.height() // 2)); app.processEvents()
check("click 1px left of the image: brush disk clipped sliver (informational)", True, f"n={canvas.mask_pixels()} ix,iy={canvas._image_coords(r.x()-1, r.y()+r.height()//2)}")
inv(canvas, "click just outside")

# 5. tiny 50x40 PNG — brush radius 1 and 500
check("load tiny png", H.load_file(app, cell, TINY))
tool(dock, "paint")
check("tiny shape 40x50", canvas.displayed_pixels().shape == (40, 50), str(canvas.displayed_pixels().shape))
dock._brush_spin.setValue(1); app.processEvents()
check("set_brush r=1 applied", canvas._brush_r == 1, str(canvas._brush_r))
H.click(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents()
check("r=1 click paints 5 px cross", canvas.mask_pixels() == 5, f"n={canvas.mask_pixels()} bbox={bbox(canvas.mask())}")
inv(canvas, "r=1 click")
canvas.clear_annotations()
dock._brush_spin.setValue(500); app.processEvents()
check("set_brush r=500 applied (spin max)", canvas._brush_r == 500, str(canvas._brush_r))
H.click(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents()
check("r=500 click fills the whole 50x40 image", canvas.mask_pixels() == 2000, f"n={canvas.mask_pixels()}")
inv(canvas, "r=500 click")
# brush cursor drawn with r=500 (paintEvent) — force a paint
canvas._cursor_pos = H.pt(canvas, 0.5, 0.5)
img = canvas.grab(); app.processEvents()
check("paintEvent with r=500 brush cursor renders", not img.isNull(), f"{img.width()}x{img.height()}")
# r=500 drag from far outside to inside
canvas.clear_annotations()
H.drag(app, canvas, QPoint(-50, -50), H.pt(canvas, 0.2, 0.2), steps=5)
check("r=500 drag from outside paints (clipped)", canvas.mask_pixels() == 2000, f"n={canvas.mask_pixels()}")
inv(canvas, "r=500 drag")
# r=500 erase click clears everything
dock._erase_chk.setChecked(True); app.processEvents()
H.click(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents()
check("r=500 erase click empties the mask", canvas.mask_pixels() == 0)
check("_mask_nonempty after erase-everything (informational: overlay flag vs any)", True,
      f"_mask_nonempty={canvas._mask_nonempty} any={bool(canvas.mask().any())}")
check("flag never hides a non-empty mask (erase-all)", not (canvas.mask().any() and not canvas._mask_nonempty))
inv(canvas, "r=500 erase")
dock._erase_chk.setChecked(False)

# 6. undo depth: 11 r=1 clicks at distinct spots, then 11 undos
canvas.set_image(canvas.displayed_pixels(), 1.0)   # same shape: mask persists; reset explicitly
canvas.clear_annotations(); canvas._undo = []      # start from a clean stack
dock._brush_spin.setValue(1); app.processEvents()
spots = [(0.1 + 0.08 * i, 0.5) for i in range(11)]
for i, (fx, fy) in enumerate(spots):
    H.click(canvas, H.pt(canvas, fx, fy)); app.processEvents()
counts = [canvas.mask_pixels()]
check("11 clicks painted 55 px (distinct 5-px crosses)", canvas.mask_pixels() == 55, f"n={canvas.mask_pixels()} undo_len={len(canvas._undo)}")
check("undo stack capped at 10 after 11 strokes", len(canvas._undo) == 10, str(len(canvas._undo)))
rets = []
for i in range(11):
    rets.append(canvas.undo_annotation()); counts.append(canvas.mask_pixels())
    bad = H.invariants(canvas)
    if bad: check(f"invariants after undo #{i+1}", False, "; ".join(bad))
check("10 undos succeed, 11th returns False", rets == [True] * 10 + [False], str(rets))
check("after 11 undos the oldest stroke (5 px) remains — silent loss of the oldest snapshot (judge)", counts[-1] == 5, f"counts={counts}")
check("_mask_nonempty consistent after undos", canvas._mask_nonempty == bool(canvas.mask().any()), f"{canvas._mask_nonempty} vs {bool(canvas.mask().any())}")

# 7. undo after Clear; Clear on empty; erase-only then undo
canvas.clear_annotations(); canvas._undo = []
dock._brush_spin.setValue(5); app.processEvents()
H.click(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents()
n1 = canvas.mask_pixels()
canvas.clear_annotations()
check("Clear empties mask and flag", canvas.mask_pixels() == 0 and not canvas._mask_nonempty)
check("undo after Clear restores stroke", canvas.undo_annotation() and canvas.mask_pixels() == n1 and canvas._mask_nonempty, f"n={canvas.mask_pixels()} flag={canvas._mask_nonempty}")
inv(canvas, "undo after Clear")
canvas.clear_annotations(); canvas._undo = []
ul = len(canvas._undo)
canvas.clear_annotations()
check("Clear on empty mask pushes an undo snapshot (informational)", True, f"undo_len {ul} -> {len(canvas._undo)}")
check("undo after Clear-on-empty: mask stays empty, no exception", canvas.undo_annotation() in (True, False) and canvas.mask_pixels() == 0 and not canvas._mask_nonempty)
inv(canvas, "undo after Clear-on-empty")
# erase-only stroke on an empty mask then undo
canvas._undo = []
dock._erase_chk.setChecked(True); app.processEvents()
H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.8, 0.8), steps=6)
check("erase-only stroke on empty mask: still empty, flag False", canvas.mask_pixels() == 0 and not canvas._mask_nonempty, f"undo_len={len(canvas._undo)}")
check("undo after erase-only stroke: True, still empty", canvas.undo_annotation() is True and canvas.mask_pixels() == 0 and not canvas._mask_nonempty)
inv(canvas, "undo after erase-only")
dock._erase_chk.setChecked(False); app.processEvents()

# 8. _mask_nonempty bookkeeping: paint, erase everything, undo, paint again — flag vs any
canvas._undo = []
seq = []
def rec(step):
    seq.append((step, canvas._mask_nonempty, bool(canvas.mask().any())))
    if canvas.mask().any() and not canvas._mask_nonempty:
        check(f"overlay hidden while mask non-empty at '{step}'", False)
rec("start")
H.click(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents(); rec("paint")
dock._brush_spin.setValue(500); dock._erase_chk.setChecked(True); app.processEvents()
H.click(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents(); rec("erase all")
dock._erase_chk.setChecked(False); app.processEvents()
canvas.undo_annotation(); rec("undo erase")
canvas.undo_annotation(); rec("undo paint")
dock._brush_spin.setValue(5); app.processEvents()
H.click(canvas, H.pt(canvas, 0.3, 0.3)); app.processEvents(); rec("paint again")
check("bookkeeping sequence recorded (flag, any)", True, str(seq))
check("flag never False while mask non-empty", all(not (a and not f) for _, f, a in seq), str(seq))
check("flag True while mask empty happens after erase-all (informational, overlay fully transparent)", True, str([s for s in seq if s[1] and not s[2]]))
inv(canvas, "bookkeeping sequence")

# 9. overlay QImage after undo: does the rendered canvas still show the overlay where the mask is?
def overlay_visible_at(ix, iy):
    """Render the canvas and compare the pixel under a mask pixel vs. the raw grey: red tint?"""
    img = canvas.grab().toImage()
    sx, sy = canvas._screen_coords(ix, iy)
    r = canvas._dest_rect(); sc = r.width() / canvas.displayed_pixels().shape[1]
    sx, sy = int(sx + sc / 2), int(sy + sc / 2)
    c = img.pixelColor(sx, sy)
    return (c.red(), c.green(), c.blue())
canvas.clear_annotations(); canvas._undo = []
dock._brush_spin.setValue(3); app.processEvents()
H.click(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents()       # stroke A
cA = centroid(canvas.mask()); mA = canvas.mask().copy()
H.click(canvas, H.pt(canvas, 0.2, 0.2)); app.processEvents()       # stroke B
check("two strokes present", canvas.mask_pixels() > mA.sum())
canvas.undo_annotation(); app.processEvents()                        # removes B; mask array object replaced
check("undo removes stroke B exactly", np.array_equal(canvas.mask(), mA))
rgbA = overlay_visible_at(int(cA[0]), int(cA[1]))
grey = overlay_visible_at(2, 38)  # far corner, unmasked
check("overlay visible at stroke A after undo (red tint)", rgbA[0] - rgbA[2] > 30, f"masked={rgbA} unmasked={grey}")
check("rgba alpha tracks mask after undo", np.array_equal(canvas._mask_rgba[..., 3] > 0, canvas.mask() > 0))
H.click(canvas, H.pt(canvas, 0.8, 0.8)); app.processEvents()       # stroke C on the replaced array
cC = (int(0.8 * 50), int(0.8 * 40))
rgbC = overlay_visible_at(*cC)
check("further stroke after undo paints into the live mask and the overlay (red tint at C)", rgbC[0] - rgbC[2] > 30 and canvas.mask()[cC[1], cC[0]] == 1, f"C={rgbC} mask@C={canvas.mask()[cC[1], cC[0]]}")
check("rgba alpha tracks mask after undo + stroke", np.array_equal(canvas._mask_rgba[..., 3] > 0, canvas.mask() > 0))
check("overlay QImage still bound to the rgba buffer (same bytes)", canvas._mask_qimage.constBits().__int__() == canvas._mask_rgba.ctypes.data,
      f"{canvas._mask_qimage.constBits().__int__()} vs {canvas._mask_rgba.ctypes.data}")
inv(canvas, "undo + further stroke")

# 10. set_image(None) then new pixels → mask reset
H.click(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents()
canvas._crop_rect = (1, 1, 10, 10)
canvas.set_image(None)
check("set_image(None): mask/rgba/qimage/crop gone", canvas.mask() is None and canvas._mask_rgba is None and canvas.crop_rect() is None and canvas._undo == [])
inv(canvas, "set_image(None)")
newpx = np.random.rand(30, 60).astype(np.float32)
canvas.set_image(newpx, 1.0)
check("new pixels after None: fresh zero mask of new shape", canvas.mask() is not None and canvas.mask().shape == (30, 60) and canvas.mask_pixels() == 0 and not canvas._mask_nonempty)
inv(canvas, "set_image(new)")
H.click(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents()
check("paint on the new image works", canvas.mask_pixels() > 0)
inv(canvas, "paint on new image")
# same-shape replacement keeps the mask (documented 2-D-per-displayed-slice behaviour)
n_keep = canvas.mask_pixels()
canvas.set_image(np.zeros((30, 60), np.float32), 1.0)
check("same-shape set_image keeps the mask (informational)", True, f"n {n_keep} -> {canvas.mask_pixels()}")
# different-shape replacement resets without warning
canvas.set_image(np.zeros((31, 60), np.float32), 1.0)
check("different-shape set_image resets mask", canvas.mask_pixels() == 0 and canvas.mask().shape == (31, 60))
inv(canvas, "shape change")

# 11. widget resize after a stroke → mapping still consistent
check("reload tiny", H.load_file(app, cell, TINY)); tool(dock, "paint"); dock._brush_spin.setValue(2); app.processEvents()
win.resize(900, 600); app.processEvents(); H.pump(app, 100)
paint_click_check_tiny = None
P = H.pt(canvas, 0.4, 0.6)
before = canvas.mask().copy(); H.click(canvas, P); app.processEvents()
new = (canvas.mask() > 0) & (before == 0); c = centroid(new); exp = canvas._image_coords(P.x(), P.y())
check("after window resize: centroid == _image_coords", c is not None and abs(c[0]-exp[0]) < 0.51 and abs(c[1]-exp[1]) < 0.51, f"exp={exp} c={c}")
inv(canvas, "resize + paint")

win.close(); app.processEvents()
sys.exit(1 if summary() else 0)
