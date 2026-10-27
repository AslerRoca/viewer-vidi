"""Repro: in rect mode on a downscaled image, a 1-widget-px drag (click jitter) replaces the
previous crop rectangle with a ~6x6 image-px sliver (guard `x1-x0 < 2` is in image px)."""
import os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from PyQt5.QtCore import QPoint
app, win = H.boot(); dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
win._ws_btn.setChecked(True); app.processEvents()
H.load_file(app, cell, sorted(glob.glob(H.FIXTURES + "/*.dcm"))[0])
tool(dock, "rect")
H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.6, 0.7))
before = canvas.crop_rect()
r = canvas._dest_rect(); print("image 1514x2044 shown in", r.width(), "x", r.height(), "widget px → 1 widget px =", round(1514 / r.width(), 1), "image px")
a = H.pt(canvas, 0.5, 0.5)
H.drag(app, canvas, a, QPoint(a.x() + 1, a.y() + 1), steps=1)       # 1-px jitter "click"
print("rect before:", before, "\nrect after 1-px drag:", canvas.crop_rect())
win.close()
sys.exit(0 if canvas.crop_rect() == before else 1)
