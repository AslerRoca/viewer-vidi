"""canvasgeom lens, part 4: zoom extremes, tool switch / load mid-stroke, double-click in
paint/rect mode, simultaneous pan + paint, large-footprint timing, 20x render with crop rect."""
import os, sys, glob, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from PyQt5.QtCore import Qt, QPoint

DCMS = sorted(glob.glob(H.FIXTURES + "/*.dcm"))
app, win = H.boot(); dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
win._ws_btn.setChecked(True); app.processEvents()
check("load CR", H.load_file(app, cell, DCMS[0])); tool(dock, "paint"); dock._brush_spin.setValue(20); app.processEvents()
Hh, Ww = canvas.displayed_pixels().shape

# zoom extremes
for _ in range(40): canvas.zoom_wheel(+120)
check("zoom clamps at 20", canvas._zoom == 20.0, str(canvas._zoom))
r = canvas._dest_rect(); check("20x dest rect is huge", r.width() > 5000, str(r))
P = wpt(canvas, 150, 150); before = canvas.mask().copy(); H.click(canvas, P); app.processEvents()
new = (canvas.mask() > 0) & (before == 0); c = centroid(new); exp = canvas._image_coords(P.x(), P.y())
check("20x paint centroid == _image_coords", c is not None and abs(c[0]-exp[0]) < 0.51 and abs(c[1]-exp[1]) < 0.51, f"exp={exp} c={c}")
tool(dock, "rect"); H.drag(app, canvas, wpt(canvas, 50, 50), wpt(canvas, 250, 250))
check("20x rect is a small image-px rect", canvas.crop_rect() is not None and 0 < canvas.crop_rect()[2] - canvas.crop_rect()[0] < 80, str(canvas.crop_rect()))
img = canvas.grab(); check("20x paintEvent with crop rect + mask renders", not img.isNull())
inv(canvas, "20x")
for _ in range(80): canvas.zoom_wheel(-120)
check("zoom clamps at 0.1", abs(canvas._zoom - 0.1) < 1e-9, str(canvas._zoom))
r = canvas._dest_rect(); check("0.1x dest rect is tiny", r.width() < 40, str(r))
tool(dock, "paint"); P = H.pt(canvas, 0.5, 0.5); before = canvas.mask().copy(); H.click(canvas, P); app.processEvents()
new = (canvas.mask() > 0) & (before == 0); c = centroid(new); exp = canvas._image_coords(P.x(), P.y())
check("0.1x paint centroid == _image_coords", c is not None and abs(c[0]-exp[0]) < 0.51 and abs(c[1]-exp[1]) < 0.51, f"exp={exp} c={c} rect={r}")
tool(dock, "rect"); H.drag(app, canvas, QPoint(r.x() + 2, r.y() + 2), QPoint(r.x() + 4, r.y() + 4), steps=2)
check("0.1x 2-widget-px drag → ~100 image px rect (informational)", True, str(canvas.crop_rect()))
inv(canvas, "0.1x")
canvas.set_image(canvas.displayed_pixels(), 1.0, reset_view=True); canvas.clear_annotations(); canvas._undo = []

# tool switch mid-stroke (paint → rect) and mid-drag (rect → paint)
tool(dock, "paint"); app.processEvents()
a, b = H.pt(canvas, 0.2, 0.5), H.pt(canvas, 0.6, 0.5)
H.press(canvas, a); H.move(canvas, QPoint((a.x()+b.x())//2, a.y()), Qt.LeftButton)
n_mid = canvas.mask_pixels()
tool(dock, "rect"); app.processEvents()           # set_wl_mode resets _stroke_last
H.move(canvas, b, Qt.LeftButton); H.release(canvas, b); app.processEvents()
check("tool switch mid-stroke: no exception, stroke stops at the switch, no rect created", canvas.mask_pixels() == n_mid and canvas.crop_rect() is None, f"n {n_mid} -> {canvas.mask_pixels()} rect={canvas.crop_rect()}")
inv(canvas, "switch mid-stroke")
H.press(canvas, a); H.move(canvas, b, Qt.LeftButton)
tool(dock, "paint"); app.processEvents()
H.move(canvas, b, Qt.LeftButton); H.release(canvas, b); app.processEvents()
check("rect→paint mid-drag: no exception, no rect, no paint", canvas.crop_rect() is None and canvas.mask_pixels() == n_mid)
inv(canvas, "switch mid-drag")

# load completes / starts mid-stroke
tool(dock, "paint"); app.processEvents()
H.press(canvas, a); H.move(canvas, QPoint((a.x()+b.x())//2, a.y()), Qt.LeftButton)
from viewer_vidi.tree_panel import _make_series_meta
cell.load_meta(_make_series_meta(DCMS[1]))      # set_image(None) under the stroke
H.move(canvas, b, Qt.LeftButton); H.release(canvas, b); app.processEvents()
check("load_meta mid-stroke: no exception; mask None until loaded", canvas.mask() is None or canvas.mask_pixels() == 0)
check("second file loads", H.wait_loaded(app, cell))
tool(dock, "paint"); app.processEvents()
check("fresh mask after load mid-stroke", canvas.mask_pixels() == 0 and canvas._undo == [] and canvas._stroke_last is None)
inv(canvas, "load mid-stroke")
# load during a polygon in progress
tool(dock, "poly"); app.processEvents()
for p in (H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.5, 0.2), H.pt(canvas, 0.5, 0.5)): H.click(canvas, p)
cell.load_meta(_make_series_meta(DCMS[0])); check("third load", H.wait_loaded(app, cell)); tool(dock, "poly"); app.processEvents()
check("polygon in progress dropped by load", canvas._poly_pts == [])
H.dclick(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents()
check("dclick with no vertices: nothing, no exception", canvas.mask_pixels() == 0 and canvas._undo == [])
inv(canvas, "load mid-polygon")

# double-click in paint / rect mode toggles fullscreen (only poly is excluded)
tool(dock, "paint"); dock._brush_spin.setValue(5); app.processEvents()
fs0 = quad.is_fullscreen()
H.dclick(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents(); H.pump(app, 100)
check("double-click in paint mode: fullscreen toggled? (informational)", True, f"fullscreen {fs0} -> {quad.is_fullscreen()} mask={canvas.mask_pixels()} undo={len(canvas._undo)}")
fs_paint = quad.is_fullscreen() != fs0
if quad.is_fullscreen() != fs0:
    H.dclick(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents(); H.pump(app, 100)   # toggle back
inv(canvas, "dclick in paint")
tool(dock, "rect"); app.processEvents()
H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.6, 0.6)); rc = canvas.crop_rect()
fs0 = quad.is_fullscreen(); H.dclick(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents(); H.pump(app, 100)
check("double-click in rect mode: fullscreen toggled?, rect kept", canvas.crop_rect() == rc, f"fullscreen {fs0} -> {quad.is_fullscreen()} rect={canvas.crop_rect()}")
fs_rect = quad.is_fullscreen() != fs0
if quad.is_fullscreen() != fs0:
    H.dclick(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents(); H.pump(app, 100)
check("fullscreen toggle on double-click in paint/rect mode (ux, informational)", True, f"paint={fs_paint} rect={fs_rect}")
inv(canvas, "dclick in rect")

# simultaneous right-button pan while painting
canvas.set_image(canvas.displayed_pixels(), 1.0, reset_view=True); canvas.clear_annotations(); canvas._undo = []
tool(dock, "paint"); dock._brush_spin.setValue(10); app.processEvents()
a = H.pt(canvas, 0.5, 0.5)
H.press(canvas, a); H.press(canvas, a, Qt.RightButton)
both = Qt.LeftButton | Qt.RightButton
for i in range(1, 6):
    H.move(canvas, QPoint(a.x() + 10 * i, a.y()), both)
H.release(canvas, QPoint(a.x() + 50, a.y()), Qt.RightButton); H.release(canvas, QPoint(a.x() + 50, a.y())); app.processEvents()
check("pan + paint simultaneously: no exception", True, f"pan=({canvas._pan_x},{canvas._pan_y}) n={canvas.mask_pixels()} bbox={bbox(canvas.mask())}")
inv(canvas, "pan+paint")

# timing: large footprints on the full CR image
canvas.set_image(canvas.displayed_pixels(), 1.0, reset_view=True); canvas.clear_annotations(); canvas._undo = []
dock._brush_spin.setValue(500); app.processEvents()
t0 = time.time(); H.drag(app, canvas, H.pt(canvas, 0.05, 0.05), H.pt(canvas, 0.95, 0.95), steps=30); dt = time.time() - t0
check("r=500 diagonal drag over 2044x1514 completes quickly", dt < 5, f"{dt:.2f}s n={canvas.mask_pixels()}")
canvas.clear_annotations(); canvas._undo = []
tool(dock, "poly"); app.processEvents(); r = canvas._dest_rect()
t0 = time.time()
for p in (QPoint(r.x()-5, r.y()-5), QPoint(r.x()+r.width()+5, r.y()-5), QPoint(r.x()+r.width()+5, r.y()+r.height()+5), QPoint(r.x()-5, r.y()+r.height()+5)): H.click(canvas, p)
H.key(canvas, Qt.Key_Return); app.processEvents(); dt = time.time() - t0
check("full-image polygon (vertices outside) fills everything quickly", canvas.mask_pixels() == Hh * Ww and dt < 3, f"{dt:.2f}s n={canvas.mask_pixels()}/{Hh*Ww}")
inv(canvas, "full-image polygon")
t0 = time.time()
for _ in range(10): canvas.undo_annotation() or None
check("undo on a 2044x1514 mask is fast", time.time() - t0 < 2, f"{time.time()-t0:.2f}s")

win.close(); app.processEvents()
sys.exit(1 if summary() else 0)
