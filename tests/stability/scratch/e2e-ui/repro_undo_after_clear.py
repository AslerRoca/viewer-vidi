"""Undo right after Clear restores the mask but not the crop rectangle (README: undo steps back through clears; Clear wipes mask and rectangle)."""
import sys
import repro_common as R
from repro_common import H
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
ws_dir = R.fresh_ws("repro_undo", ["bpd1_20100102_1.dcm"])
app, win = H.boot(); dock = win._dock; canvas = win._quad.active_cell().canvas()
win._ws_btn.setChecked(True); app.processEvents()
R.open_dir(app, win, ws_dir)
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.5, 0.3))
QTest.mouseClick(dock._tool_btns["rect"], Qt.LeftButton); app.processEvents()
H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.7, 0.7))
print("before Clear: mask px", canvas.mask_pixels(), "rect", canvas.crop_rect())
QTest.mouseClick(dock._clear_btn, Qt.LeftButton); app.processEvents()
print("after Clear:  mask px", canvas.mask_pixels(), "rect", canvas.crop_rect())
R.ctrl(app, win, canvas, Qt.Key_Z)
print("after Ctrl+Z: mask px", canvas.mask_pixels(), "rect", canvas.crop_rect())
win.close(); sys.exit(0 if canvas.crop_rect() is not None else 1)
