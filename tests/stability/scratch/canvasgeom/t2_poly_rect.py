"""canvasgeom lens, part 2: polygon tool (degenerate / self-intersecting / outside vertices,
zoom+pan mapping) and rect tool (clipping, reversed, 1-px, borders, zoom/pan, mid-drag zoom)."""
import os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import numpy as np
from PyQt5.QtCore import Qt, QPoint
from matplotlib.path import Path as MplPath

D = os.path.dirname(os.path.abspath(__file__))
DCM = sorted(glob.glob(H.FIXTURES + "/*.dcm"))[0]
TINY = os.path.join(D, "ws50", "tiny_50x40.png")

app, win = H.boot()
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
win._ws_btn.setChecked(True); app.processEvents()

def ipt(ix, iy):
    """Widget point at the centre of image pixel (ix, iy)."""
    r = canvas._dest_rect(); w = canvas.displayed_pixels().shape[1]; h = canvas.displayed_pixels().shape[0]
    return QPoint(int(r.x() + (ix + 0.5) * r.width() / w), int(r.y() + (iy + 0.5) * r.height() / h))

def poly(points, finish="dclick"):
    for p in points:
        H.click(canvas, p)
    app.processEvents()
    if finish == "dclick":
        H.dclick(canvas, points[-1])
    elif finish == "enter":
        H.key(canvas, Qt.Key_Return)
    elif finish == "esc":
        H.key(canvas, Qt.Key_Escape)
    app.processEvents()

def expected_fill(verts, shape):
    """Reference even-odd rasterisation: pixel centres inside the polygon."""
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w]
    pts = np.c_[xx.ravel() + 0.5, yy.ravel() + 0.5]
    return MplPath(verts).contains_points(pts).reshape(h, w)

# ── tiny image: exact pixel semantics ────────────────────────────────────────
check("load tiny png", H.load_file(app, cell, TINY)); tool(dock, "poly"); app.processEvents()
ul = len(canvas._undo)
poly([ipt(10, 10), ipt(30, 30)])
check("2-point polygon (dclick) cancels: no fill, no undo entry, pts cleared", canvas.mask_pixels() == 0 and len(canvas._undo) == ul and canvas._poly_pts == [], f"n={canvas.mask_pixels()} undo={len(canvas._undo)} pts={canvas._poly_pts}")
inv(canvas, "2-pt polygon")
poly([ipt(10, 10), ipt(30, 30)], finish="enter")
check("2-point polygon (Enter) cancels", canvas.mask_pixels() == 0 and len(canvas._undo) == ul and canvas._poly_pts == [])
# single click + dclick (1 distinct vertex)
poly([ipt(20, 20)])
check("1-point polygon cancels", canvas.mask_pixels() == 0 and len(canvas._undo) == ul and canvas._poly_pts == [])
# collinear
poly([ipt(5, 20), ipt(25, 20), ipt(45, 20)])
check("collinear 3 points: no fill, no exception (undo entry pushed: informational)", canvas.mask_pixels() == 0, f"n={canvas.mask_pixels()} undo {ul}->{len(canvas._undo)}")
inv(canvas, "collinear polygon")
canvas._undo = []
# consecutive duplicate clicks collapse to one vertex
for p in (ipt(10, 10), ipt(10, 10), ipt(10, 10), ipt(30, 10)):
    H.click(canvas, p)
app.processEvents()
check("consecutive duplicate clicks collapse to one vertex", canvas._poly_pts == [(10, 10), (30, 10)], str(canvas._poly_pts))
H.key(canvas, Qt.Key_Escape); app.processEvents()
check("Esc cancels the polygon in progress", canvas._poly_pts == [] and canvas.mask_pixels() == 0)
# non-consecutive duplicates A,B,A,C
poly([ipt(10, 10), ipt(30, 10), ipt(10, 10), ipt(30, 30)])
check("A,B,A,C polygon: no exception", True, f"n={canvas.mask_pixels()} pts={canvas._poly_pts}")
inv(canvas, "A,B,A,C polygon")
canvas.clear_annotations(); canvas._undo = []
# axis-aligned square polygon 10..30 — pixel coverage convention
poly([ipt(10, 10), ipt(30, 10), ipt(30, 30), ipt(10, 30)])
n_sq = canvas.mask_pixels(); bb = bbox(canvas.mask())
check("square polygon (10,10)-(30,30): coverage (informational: 400 = half-open, 441 = inclusive)", n_sq in (400, 441), f"n={n_sq} bbox={bb}")
exp = expected_fill([(10.5, 10.5), (30.5, 10.5), (30.5, 30.5), (10.5, 30.5)], canvas.mask().shape)
check("square polygon matches reference rasterisation at the clicked pixel centres", np.array_equal(canvas.mask() > 0, exp), f"diff={int((canvas.mask()>0).astype(int).sum() - exp.sum())}")
inv(canvas, "square polygon")
# right-click drops last vertex
canvas.clear_annotations(); canvas._undo = []
for p in (ipt(10, 10), ipt(30, 10), ipt(30, 30)):
    H.click(canvas, p)
H.click(canvas, ipt(30, 30), button=Qt.RightButton); app.processEvents()
check("right-click drops the last vertex", canvas._poly_pts == [(10, 10), (30, 10)], str(canvas._poly_pts))
H.dclick(canvas, ipt(30, 10)); app.processEvents()   # dclick at the same point as last vertex: no new vertex → 2 pts → cancel
check("dclick after dropping to 2 vertices cancels (no fill)", canvas.mask_pixels() == 0 and canvas._poly_pts == [], f"n={canvas.mask_pixels()}")
# self-intersecting: bow-tie and pentagram
canvas.clear_annotations(); canvas._undo = []
poly([ipt(5, 5), ipt(45, 35), ipt(45, 5), ipt(5, 35)])
exp = expected_fill([(5.5, 5.5), (45.5, 35.5), (45.5, 5.5), (5.5, 35.5)], canvas.mask().shape)
agree = ((canvas.mask() > 0) == exp).mean()
check("bow-tie polygon: both lobes filled, matches even-odd reference", canvas.mask_pixels() > 0 and agree > 0.97, f"n={canvas.mask_pixels()} agree={agree:.3f}")
inv(canvas, "bow-tie")
canvas.clear_annotations(); canvas._undo = []
# pentagram centred at (25,20) radius 18
ang = [np.deg2rad(-90 + 144 * k) for k in range(5)]
star = [(25 + 18 * np.cos(a), 20 + 18 * np.sin(a)) for a in ang]
star_i = [(int(round(x)), int(round(y))) for x, y in star]
poly([ipt(x, y) for x, y in star_i])
centre = int(canvas.mask()[20, 25])
exp_eo = expected_fill([(x + 0.5, y + 0.5) for x, y in star_i], canvas.mask().shape)
check("pentagram polygon: no exception, filled", canvas.mask_pixels() > 0)
check("pentagram centre pixel (informational: 0 = even-odd hole, 1 = winding fill)", True, f"centre={centre} n={canvas.mask_pixels()} even-odd-ref={int(exp_eo.sum())} agree={((canvas.mask()>0)==exp_eo).mean():.3f}")
inv(canvas, "pentagram")
# vertices far outside the image: triangle with two vertices off-canvas
canvas.clear_annotations(); canvas._undo = []
r = canvas._dest_rect()
far = [QPoint(r.x() - 400, r.y() - 300), QPoint(r.x() + r.width() + 400, r.y() - 300), ipt(25, 35)]
verts = [canvas._image_coords(p.x(), p.y()) for p in far]
poly(far)
exp = expected_fill([(x + 0.5, y + 0.5) for x, y in verts], canvas.mask().shape)
agree = ((canvas.mask() > 0) == exp).mean()
check("triangle with 2 vertices far outside: clipped fill matches reference", canvas.mask_pixels() > 0 and agree > 0.97, f"verts={verts} n={canvas.mask_pixels()} ref={int(exp.sum())} agree={agree:.3f}")
inv(canvas, "far-outside triangle")
canvas.clear_annotations(); canvas._undo = []
# polygon entirely outside (left of image)
far = [QPoint(r.x() - 300, r.y()), QPoint(r.x() - 100, r.y()), QPoint(r.x() - 100, r.y() + 50)]
poly(far)
check("polygon entirely outside: nothing filled, no exception", canvas.mask_pixels() == 0, f"n={canvas.mask_pixels()} undo={len(canvas._undo)}")
inv(canvas, "outside polygon")
# polygon whose bbox overlaps the image but whose area does not (corner cut)
canvas.clear_annotations(); canvas._undo = []
far = [QPoint(r.x() - 200, r.y() + 10), QPoint(r.x() + 10, r.y() - 200), QPoint(r.x() - 200, r.y() - 200)]
poly(far)
check("corner-cut polygon (bbox overlaps, area outside): nothing filled", canvas.mask_pixels() == 0, f"n={canvas.mask_pixels()}")
inv(canvas, "corner-cut polygon")
# erase-mode polygon
canvas.clear_annotations(); canvas._undo = []
tool(dock, "paint"); dock._brush_spin.setValue(500); app.processEvents(); H.click(canvas, ipt(25, 20)); app.processEvents()
tool(dock, "poly"); dock._erase_chk.setChecked(True); app.processEvents()
poly([ipt(10, 10), ipt(30, 10), ipt(30, 30), ipt(10, 30)])
check("polygon with Erase ticked erases inside (informational)", True, f"n={canvas.mask_pixels()} (2000 - 400/441?) flag={canvas._mask_nonempty}")
check("erase polygon keeps flag consistent", not (canvas.mask().any() and not canvas._mask_nonempty))
inv(canvas, "erase polygon")
dock._erase_chk.setChecked(False); app.processEvents()

# ── CR DICOM: polygon under zoom + pan vs reference ──────────────────────────
check("load CR dicom", H.load_file(app, cell, DCM)); tool(dock, "poly"); app.processEvents()
for _ in range(5): canvas.zoom_wheel(+120)
H.drag(app, canvas, wpt(canvas, 200, 200), wpt(canvas, 150, 260), steps=5, button=Qt.RightButton)
r = canvas._dest_rect()
P = [wpt(canvas, 40, 60), wpt(canvas, 250, 90), wpt(canvas, 220, 300), wpt(canvas, 60, 330)]
verts = [canvas._image_coords(p.x(), p.y()) for p in P]
poly(P)
exp = expected_fill([(x + 0.5, y + 0.5) for x, y in verts], canvas.mask().shape)
agree = ((canvas.mask() > 0) == exp)
check("zoomed+panned polygon fill matches reference polygon of _image_coords vertices", canvas.mask_pixels() > 1000 and agree.mean() > 0.999 and abs(int(canvas.mask_pixels()) - int(exp.sum())) < 0.01 * exp.sum(),
      f"zoom={canvas._zoom:.2f} pan=({canvas._pan_x},{canvas._pan_y}) verts={verts} n={canvas.mask_pixels()} ref={int(exp.sum())} mismatch={int((~agree).sum())}")
inv(canvas, "zoomed polygon")
# polygon in progress + grab (rubber line drawing with cursor) — no exception
H.click(canvas, wpt(canvas, 100, 100)); H.move(canvas, wpt(canvas, 150, 150)); app.processEvents()
img = canvas.grab(); check("paintEvent with polygon in progress renders", not img.isNull())
H.key(canvas, Qt.Key_Escape)

# ── rect tool ────────────────────────────────────────────────────────────────
canvas.set_image(canvas.displayed_pixels(), 1.0, reset_view=True); canvas.clear_annotations()
tool(dock, "rect"); app.processEvents()
Hh, Ww = canvas.displayed_pixels().shape
r = canvas._dest_rect()
def rdrag(a, b, steps=6):
    H.drag(app, canvas, a, b, steps=steps)
    return canvas.crop_rect()
# baseline rect
rc = rdrag(H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.6, 0.7))
a_i = canvas._image_coords(*[H.pt(canvas, 0.2, 0.2).x(), H.pt(canvas, 0.2, 0.2).y()]); b_i = canvas._image_coords(H.pt(canvas, 0.6, 0.7).x(), H.pt(canvas, 0.6, 0.7).y())
check("rect equals (_image_coords(a), _image_coords(b)+1)", rc == (a_i[0], a_i[1], b_i[0] + 1, b_i[1] + 1), f"rect={rc} a={a_i} b={b_i}")
inv(canvas, "baseline rect")
base = rc
# reversed direction gives the same rect
rc2 = rdrag(H.pt(canvas, 0.6, 0.7), H.pt(canvas, 0.2, 0.2))
check("reversed drag gives the same rect", rc2 == base, f"{rc2} vs {base}")
# 1-px drag keeps previous
a = H.pt(canvas, 0.5, 0.5); rc3 = rdrag(a, QPoint(a.x() + 1, a.y() + 1), steps=1)
check("1-px drag keeps the previous rect", rc3 == base, f"{rc3}")
rc3b = rdrag(a, a, steps=1)
check("click (no move) keeps the previous rect", rc3b == base, f"{rc3b}")
inv(canvas, "1-px drag")
# outside → inside: clipped at 0
rc4 = rdrag(QPoint(r.x() - 60, r.y() - 40), H.pt(canvas, 0.4, 0.4))
check("drag from outside top-left clips to (0,0,..)", rc4 is not None and rc4[0] == 0 and rc4[1] == 0 and rc4[2] > 0 and rc4[3] > 0, f"{rc4}")
inv(canvas, "outside->inside rect")
# inside → outside bottom-right: clipped at w,h
rc5 = rdrag(H.pt(canvas, 0.5, 0.5), QPoint(r.x() + r.width() + 70, r.y() + r.height() + 70))
check("drag into outside bottom-right clips to (w,h)", rc5 is not None and rc5[2] == Ww and rc5[3] == Hh, f"{rc5} w,h={Ww},{Hh}")
inv(canvas, "inside->outside rect")
prev = rc5
# entirely outside (left, right, above, below) keeps previous
for name, (a, b) in {
    "left":  (QPoint(r.x() - 80, r.y() + 50), QPoint(r.x() - 10, r.y() + 150)),
    "right": (QPoint(r.x() + r.width() + 5, r.y() + 50), QPoint(r.x() + r.width() + 60, r.y() + 150)),
    "above": (QPoint(r.x() + 50, r.y() - 80), QPoint(r.x() + 150, r.y() - 10)),
    "below": (QPoint(r.x() + 50, r.y() + r.height() + 5), QPoint(r.x() + 150, r.y() + r.height() + 80)),
}.items():
    rcx = rdrag(a, b)
    check(f"drag entirely outside ({name}) keeps previous rect", rcx == prev, f"{rcx} vs {prev}")
    bad = H.invariants(canvas)
    if bad: check(f"invariants after outside-{name}", False, "; ".join(bad))
# exact border drag: corner to corner
rc6 = rdrag(QPoint(r.x(), r.y()), QPoint(r.x() + r.width(), r.y() + r.height()))
check("corner-to-corner drag gives the full image rect", rc6 == (0, 0, Ww, Hh), f"{rc6}")
rc7 = rdrag(QPoint(r.x(), r.y()), QPoint(r.x() + r.width() - 1, r.y() + r.height() - 1))
check("drag to last widget px of the image rect still reaches w,h", rc7 == (0, 0, Ww, Hh), f"{rc7}")
inv(canvas, "border rects")
# after zoom + pan
for _ in range(6): canvas.zoom_wheel(+120)
H.drag(app, canvas, wpt(canvas, 200, 200), wpt(canvas, 120, 150), steps=5, button=Qt.RightButton)
a, b = wpt(canvas, 30, 40), wpt(canvas, 260, 330)
rc8 = rdrag(a, b)
ai, bi = canvas._image_coords(a.x(), a.y()), canvas._image_coords(b.x(), b.y())
check("zoomed+panned rect equals _image_coords of the drag end points", rc8 == (ai[0], ai[1], bi[0] + 1, bi[1] + 1), f"rect={rc8} a={ai} b={bi} zoom={canvas._zoom:.2f}")
inv(canvas, "zoomed rect")
img = canvas.grab(); check("paintEvent with crop rect partially off-widget renders", not img.isNull())
# zoom during a rect drag: start point is a widget point; which mapping wins?
canvas.set_image(canvas.displayed_pixels(), 1.0, reset_view=True); app.processEvents()
a, b = H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.7, 0.7)
ai_before = canvas._image_coords(a.x(), a.y())
H.press(canvas, a); H.move(canvas, QPoint((a.x()+b.x())//2, (a.y()+b.y())//2), Qt.LeftButton)
for _ in range(4): canvas.zoom_wheel(+120)
H.move(canvas, b, Qt.LeftButton); H.release(canvas, b); app.processEvents()
ai_after = canvas._image_coords(a.x(), a.y()); bi_after = canvas._image_coords(b.x(), b.y())
rc9 = canvas.crop_rect()
check("zoom mid-drag: rect start re-mapped in the NEW geometry (informational)", True, f"rect={rc9} start@old={ai_before} start@new={ai_after} end@new={bi_after}")
inv(canvas, "zoom mid-drag rect")
# Clear wipes the rect; undo restores the mask only
canvas.set_image(canvas.displayed_pixels(), 1.0, reset_view=True); canvas.clear_annotations(); canvas._undo = []
rc10 = rdrag(H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.6, 0.6))
tool(dock, "paint"); dock._brush_spin.setValue(20); app.processEvents(); H.click(canvas, H.pt(canvas, 0.4, 0.4)); app.processEvents()
n_before = canvas.mask_pixels()
canvas.clear_annotations()
check("Clear wipes mask and rect", canvas.mask_pixels() == 0 and canvas.crop_rect() is None)
ok = canvas.undo_annotation()
check("undo after Clear restores the mask but NOT the rect (README: undo steps back through clears)", ok and canvas.mask_pixels() == n_before and canvas.crop_rect() == rc10,
      f"mask {canvas.mask_pixels()}/{n_before} rect={canvas.crop_rect()} (was {rc10})")
inv(canvas, "undo after Clear w/ rect")
# rect persists across same-shape set_image, reset on shape change
tool(dock, "rect"); app.processEvents()
rc11 = rdrag(H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.6, 0.6))
canvas.set_image(canvas.displayed_pixels().copy(), 1.0, reset_view=False)
check("same-shape set_image keeps the rect (informational)", True, f"{canvas.crop_rect()} vs {rc11}")
canvas.set_image(np.zeros((100, 120), np.float32), 1.0)
check("shape change drops the rect", canvas.crop_rect() is None)
inv(canvas, "rect after shape change")
# rect on a tiny image: 2-px minimum
check("load tiny", H.load_file(app, cell, TINY)); tool(dock, "rect"); app.processEvents()
rc12 = rdrag(ipt(10, 10), ipt(11, 11))
check("2x2 image-px drag on tiny image accepted as the minimum rect", rc12 == (10, 10, 12, 12), f"{rc12}")
rc13 = rdrag(ipt(20, 20), ipt(20, 21))
check("1-col-wide drag keeps previous", rc13 == rc12, f"{rc13}")
rc14 = rdrag(ipt(0, 0), ipt(49, 39))
check("tiny full-image drag", rc14 == (0, 0, 50, 40), f"{rc14}")
inv(canvas, "tiny rects")

win.close(); app.processEvents()
sys.exit(1 if summary() else 0)
