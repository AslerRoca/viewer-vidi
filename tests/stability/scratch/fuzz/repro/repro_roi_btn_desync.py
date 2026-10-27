"""The panel's own 'ROI' W/L button switches the canvas to 'roi' and back to 'drag',
ignoring the dock's selected tool; the dock keeps showing Brush as active."""
from common import *
app, win = H.boot(); dock, quad = win._dock, win._quad
ws = H.open_workspace(app, win, fresh_ws("roi"), "image")
cell = quad.active_cell(); canvas = cell.canvas()
print("after opening workspace: dock tool =", dock._current_tool(), "canvas mode =", canvas.wl_mode())
cell._roi_btn.setChecked(True); app.processEvents()
print("ROI button on :          canvas mode =", canvas.wl_mode(), "| dock Brush checked =", dock._tool_btns["paint"].isChecked())
cell._roi_btn.setChecked(False); app.processEvents()
print("ROI button off:          canvas mode =", canvas.wl_mode(), "| dock Brush checked =", dock._tool_btns["paint"].isChecked())
wl0 = canvas.wl()
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.6, 0.3))
print("brush drag -> mask_pixels =", canvas.mask_pixels(), " W/L changed:", canvas.wl() != wl0)
ok = canvas.wl_mode() == "paint" and canvas.mask_pixels() > 0
print("RESULT:", "PASS" if ok else "FAIL (expected the dock's Brush tool to be restored after the ROI button is released)")
win.close(); app.processEvents(); sys.exit(0 if ok else 1)
