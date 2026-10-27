"""Rect crop off-by-one and brush-centre truncation, at high zoom so 1 image px = several screen px."""
from common import *
import numpy as np
from PyQt5.QtCore import QPoint
app, win = H.boot()
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
# small synthetic image so the mapping is simple: 40x30, fit in 1400x900 widget → ~ many screen px per image px
from PIL import Image
img = (np.arange(30*40, dtype=np.uint8).reshape(30,40))
p = os.path.join(SCR, "ws", "p01.png"); os.makedirs(os.path.dirname(p), exist_ok=True); Image.fromarray(img, "L").save(p)
win._ws_btn.setChecked(True); app.processEvents()
assert H.load_file(app, cell, p)
r = canvas._dest_rect(); W, Hh = canvas._qimage.width(), canvas._qimage.height()
sx = r.width() / W; sy = r.height() / Hh
print("dest", r, "scale per image px:", sx, sy)
def spt(ix, iy, fx=0.5, fy=0.5):
    """screen point at image pixel (ix,iy) + fraction inside that pixel"""
    return QPoint(int(r.x() + (ix + fx) * sx), int(r.y() + (iy + fy) * sy))
# 1. rect from inside pixel (5,4) to inside pixel (20,17): user visually covers 5..20 and 4..17 inclusive
dock._tool_btns["rect"].setChecked(True); dock._apply_tool()
a, b = spt(5, 4, 0.2, 0.2), spt(20, 17, 0.8, 0.8)
H.drag(app, canvas, a, b)
rect = canvas.crop_rect()
check("rect covers pixels under both drag ends inclusive (x0,y0,x1,y1)=(5,4,21,18)", rect == (5, 4, 21, 18), str(rect))
# screen rectangle drawn: compare against the drag endpoints
sx0, sy0 = canvas._screen_coords(rect[0], rect[1]); sx1, sy1 = canvas._screen_coords(rect[2], rect[3])
print("drawn screen rect", (sx0, sy0, sx1 - 1, sy1 - 1), "drag", (a.x(), a.y(), b.x(), b.y()))
check("drawn rect contains both drag endpoints", sx0 <= a.x() <= sx1 - 1 and sy0 <= a.y() <= sy1 - 1 and sx0 <= b.x() <= sx1 - 1 and sy0 <= b.y() <= sy1 - 1)
# 2. reversed drag (bottom-right → top-left)
H.drag(app, canvas, b, a)
check("reversed drag gives the same rect", canvas.crop_rect() == (5, 4, 21, 18), str(canvas.crop_rect()))
# 3. drag beyond image edges clamps to full image
H.drag(app, canvas, QPoint(r.x() - 30, r.y() - 30), QPoint(r.right() + 30, r.bottom() + 30))
check("drag beyond edges → full image rect", canvas.crop_rect() == (0, 0, W, Hh), str(canvas.crop_rect()))
# 4. drag ending exactly on the last image pixel row/col (bottom-right corner inside)
H.drag(app, canvas, spt(0, 0, 0.1, 0.1), spt(W - 1, Hh - 1, 0.9, 0.9))
check("drag to last pixel → x1==W, y1==H", canvas.crop_rect() == (0, 0, W, Hh), str(canvas.crop_rect()))
# 5. 1-px wide sliver is ignored, previous rect kept
prev = canvas.crop_rect()
H.drag(app, canvas, spt(3, 3, 0.2, 0.2), spt(3, 9, 0.8, 0.8))
check("1-px-wide drag keeps previous rect", canvas.crop_rect() == prev, str(canvas.crop_rect()))
# 6. crop slice shape equals visible coverage
H.drag(app, canvas, spt(5, 4, 0.2, 0.2), spt(20, 17, 0.8, 0.8))
x0, y0, x1, y1 = canvas.crop_rect()
sub = canvas.displayed_pixels()[y0:y1, x0:x1]
check("crop slice is 16x14 (inclusive coverage)", sub.shape == (14, 16), str(sub.shape))
# 7. brush centre: click at fraction 0.9 inside pixel (12, 9) with radius 1 → centre must be (12, 9)
dock._tool_btns["paint"].setChecked(True); dock._apply_tool(); dock._brush_spin.setValue(1)
canvas.clear_annotations()
H.click(canvas, spt(12, 9, 0.9, 0.9)); app.processEvents()
ys, xs = np.nonzero(canvas.mask())
check("brush stamp centred on the pixel under the cursor (12,9)", (round(xs.mean()), round(ys.mean())) == (12, 9), f"centre {(xs.mean(), ys.mean())} n={len(xs)}")
H.click(canvas, spt(12, 9, 0.05, 0.05)); app.processEvents()
ys, xs = np.nonzero(canvas.mask())
check("same pixel from its top-left corner → same stamp", (round(xs.mean()), round(ys.mean())) == (12, 9) and len(xs) == 5, f"n={len(xs)}")
# 8. polygon over a known square: vertices at pixel centres (5,5),(15,5),(15,15),(5,15)
dock._tool_btns["poly"].setChecked(True); dock._apply_tool(); canvas.clear_annotations()
for q in ((5,5),(15,5),(15,15),(5,15)):
    H.click(canvas, spt(*q))
H.key(canvas, H.__dict__["Qt"].Key_Return if "Qt" in H.__dict__ else __import__("PyQt5.QtCore", fromlist=["Qt"]).Qt.Key_Return)
app.processEvents()
m = canvas.mask(); ys, xs = np.nonzero(m)
print("poly bbox", xs.min(), xs.max(), ys.min(), ys.max(), "n", len(xs))
check("polygon fill covers 5..15 inclusive square (121 px) or at least 10x10", 100 <= len(xs) <= 121 and xs.min() == 5 and ys.min() == 5, f"n={len(xs)} bbox x{xs.min()}-{xs.max()} y{ys.min()}-{ys.max()}")
check("invariants", not H.invariants(canvas), str(H.invariants(canvas)))
win.close(); app.processEvents()
sys.exit(summary())
