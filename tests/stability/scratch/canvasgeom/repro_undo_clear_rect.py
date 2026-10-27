"""Repro: Clear wipes mask + crop rect; undo restores the mask only — the rectangle is gone."""
import os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
app, win = H.boot(); dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
win._ws_btn.setChecked(True); app.processEvents()
H.load_file(app, cell, sorted(glob.glob(H.FIXTURES + "/*.dcm"))[0])
tool(dock, "rect"); H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.6, 0.6))
rect_before = canvas.crop_rect()
tool(dock, "paint"); H.click(canvas, H.pt(canvas, 0.4, 0.4)); app.processEvents()
n_before = canvas.mask_pixels()
dock._clear_btn.click() if hasattr(dock, "_clear_btn") else canvas.clear_annotations()
app.processEvents()
print("after Clear: mask", canvas.mask_pixels(), "rect", canvas.crop_rect())
dock.undo(); app.processEvents()
print("after Undo : mask", canvas.mask_pixels(), "(was", n_before, ") rect", canvas.crop_rect(), "(was", rect_before, ")")
win.close()
sys.exit(0 if canvas.crop_rect() == rect_before else 1)
