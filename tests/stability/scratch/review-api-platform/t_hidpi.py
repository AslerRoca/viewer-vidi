"""HiDPI probe (run with QT_SCALE_FACTOR=1 and =2): logical-vs-device mapping of brush stamp,
mask overlay in grab(), brush cursor ring radius, crop rect from a drag."""
import os, sys
from common import *
import harness as H
import numpy as np
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling); QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
app, win = H.boot()
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
fix = os.path.join(FIX, sorted(os.listdir(FIX))[0])
check("fixture loads", H.load_file(app, cell, fix))
win._ws_btn.setChecked(True); app.processEvents()
dpr = canvas.devicePixelRatioF()
print("QT_SCALE_FACTOR", os.environ.get("QT_SCALE_FACTOR"), "dpr", dpr, "canvas logical", canvas.width(), canvas.height())
Hh, Ww = canvas.displayed_pixels().shape
r = canvas._dest_rect(); print("dest_rect", r)

def to_np(pm):
    im = pm.toImage().convertToFormat(QImage.Format_RGB888)
    ptr = im.constBits(); ptr.setsize(im.sizeInBytes())
    return np.frombuffer(ptr, np.uint8).reshape(im.height(), im.bytesPerLine())[:, :im.width() * 3].reshape(im.height(), im.width(), 3).copy()

pm = canvas.grab()
check("grab() size = logical*dpr", (pm.width(), pm.height()) == (round(canvas.width() * dpr), round(canvas.height() * dpr)), f"{pm.width()}x{pm.height()} dpr={pm.devicePixelRatio()}")
a = to_np(pm)
nonblack = np.argwhere(a.max(axis=2) > 0)
y0, x0 = nonblack.min(axis=0); y1, x1 = nonblack.max(axis=0)
print("image rect in device px:", (x0, y0, x1, y1), "expected", (r.x() * dpr, r.y() * dpr, (r.right()) * dpr, (r.bottom()) * dpr))
check("drawn image rect in grab matches _dest_rect*dpr (±2 dev px)",
      abs(x0 - r.x() * dpr) <= 2 and abs(y0 - r.y() * dpr) <= 2 and abs(x1 - (r.x() + r.width()) * dpr) <= 3 and abs(y1 - (r.y() + r.height()) * dpr) <= 3,
      f"got {(x0, y0, x1, y1)}")

# brush click at logical centre
p = H.pt(canvas, 0.5, 0.5)
dock._brush_spin.setValue(40); app.processEvents()
H.click(canvas, p); app.processEvents()
ix, iy = canvas._image_coords(p.x(), p.y())
ys, xs = np.nonzero(canvas._mask)
check("stamp centred on _image_coords(click)", abs(xs.mean() - ix) < 1 and abs(ys.mean() - iy) < 1, f"({xs.mean():.1f},{ys.mean():.1f}) vs ({ix},{iy}) — image px ({Ww//2},{Hh//2})")
a = to_np(canvas.grab())
red = np.argwhere((a[..., 0].astype(int) - a[..., 1] > 40) & (a[..., 0].astype(int) - a[..., 2] > 40))
cy, cx = red.mean(axis=0)
rad_dev = (red[:, 1].max() - red[:, 1].min()) / 2.0
exp_rad_dev = 40 * r.width() / Ww * dpr
print(f"overlay blob centre device=({cx:.1f},{cy:.1f}) /dpr=({cx/dpr:.1f},{cy/dpr:.1f}) click logical=({p.x()},{p.y()}); radius dev={rad_dev:.1f} expected={exp_rad_dev:.1f}")
check("overlay blob centre (device/dpr) == logical click (±2)", abs(cx / dpr - p.x()) <= 2 and abs(cy / dpr - p.y()) <= 2)
check("overlay blob radius in device px == brush_r*scale*dpr (±15%)", abs(rad_dev - exp_rad_dev) <= 0.15 * exp_rad_dev + 1)

# brush cursor ring: clear mask, set cursor, look for the white ring along the horizontal through the centre
canvas.clear_annotations(); canvas._cursor_pos = p; canvas.update(); app.processEvents()
a = to_np(canvas.grab())
row = a[int(round(p.y() * dpr))]
bright = np.where((row.min(axis=1) > 150) & (np.abs(row[:, 0].astype(int) - row[:, 2].astype(int)) < 20))[0]
left = bright[bright < p.x() * dpr]; right = bright[bright > p.x() * dpr]
if len(left) and len(right):
    ring_rad = (right.min() - left.max()) / 2.0
    print(f"cursor ring radius device={ring_rad:.1f} expected={exp_rad_dev:.1f}")
    check("brush cursor ring radius matches the stamp radius (±15%)", abs(ring_rad - exp_rad_dev) <= 0.15 * exp_rad_dev + 2, f"{ring_rad:.1f} vs {exp_rad_dev:.1f}")
else:
    check("brush cursor ring detectable", False, f"bright cols on row: {bright[:10]}")

# crop rect from a logical drag
dock._tool_btns["rect"].setChecked(True); dock._apply_tool()
a0, b0 = H.pt(canvas, 0.25, 0.25), H.pt(canvas, 0.75, 0.75)
H.drag(app, canvas, a0, b0)
cr = canvas.crop_rect(); ea = canvas._image_coords(a0.x(), a0.y()); eb = canvas._image_coords(b0.x(), b0.y())
check("crop rect == image coords of the logical drag endpoints", cr == (ea[0], ea[1], eb[0] + 1, eb[1] + 1), f"{cr} vs {ea},{eb}")
# dim region in grab: pixels outside the rect darker than inside
a = to_np(canvas.grab())
sx0, sy0 = canvas._screen_coords(cr[0], cr[1]); sx1, sy1 = canvas._screen_coords(cr[2], cr[3])
inside = a[int((sy0 + 5) * dpr):int((sy1 - 5) * dpr), int((sx0 + 5) * dpr):int((sx1 - 5) * dpr)].mean()
outside = a[int((r.y() + 2) * dpr):int((sy0 - 3) * dpr), int((r.x() + 2) * dpr):int((r.x() + r.width() - 2) * dpr)].mean()
check("outside of crop rect dimmed in grab", outside < inside, f"inside={inside:.1f} outside={outside:.1f}")
# polygon via logical clicks
dock._tool_btns["poly"].setChecked(True); dock._apply_tool(); canvas.clear_annotations()
for q in (H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.6, 0.3), H.pt(canvas, 0.6, 0.6)): H.click(canvas, q)
H.dclick(canvas, H.pt(canvas, 0.3, 0.6)); app.processEvents()
ys, xs = np.nonzero(canvas._mask); exp_c = ((0.3 + 0.6) / 2 * Ww, (0.3 + 0.6) / 2 * Hh)
check("polygon fill centroid at expected image coords (±1%)", abs(xs.mean() - exp_c[0]) < 0.01 * Ww and abs(ys.mean() - exp_c[1]) < 0.01 * Hh, f"({xs.mean():.0f},{ys.mean():.0f}) vs {exp_c}")
win.close(); app.processEvents()
sys.exit(summary())
