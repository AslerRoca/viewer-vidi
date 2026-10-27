"""Undo after Clear restores the mask but not the rectangle that Clear dropped."""
from common import *
app, win = H.boot(); dock, quad = win._dock, win._quad
ws = H.open_workspace(app, win, fresh_ws("undo"), "image")
cell = quad.active_cell(); canvas = cell.canvas()
dock._tool_btns["rect"].click(); H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.6, 0.6))
dock._tool_btns["paint"].click(); H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.5, 0.3))
px0, rect0 = canvas.mask_pixels(), canvas.crop_rect()
print("before Clear: mask_px =", px0, "rect =", rect0)
dock._clear_btn.click(); app.processEvents()
print("after Clear:  mask_px =", canvas.mask_pixels(), "rect =", canvas.crop_rect())
dock._undo_btn.click(); app.processEvents()
print("after Undo:   mask_px =", canvas.mask_pixels(), "rect =", canvas.crop_rect(), "| status:", repr(dock._status_lbl.text()))
ok = canvas.mask_pixels() == px0 and canvas.crop_rect() == rect0
print("RESULT:", "PASS" if ok else "FAIL (README: Undo steps back through clears; Clear wipes mask AND rectangle)")
win.close(); app.processEvents(); sys.exit(0 if ok else 1)
