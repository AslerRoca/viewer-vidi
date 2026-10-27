"""README: 'Undo steps back through strokes / polygons / clears; Clear wipes mask and rectangle' → does Undo after Clear restore the rectangle?"""
from common import *
app, win = H.boot(); dock, quad = win._dock, win._quad
ws = H.open_workspace(app, win, fresh_ws("p08", [os.path.join(FIX, "bpd1_20100101_1.dcm")]))
c = quad.active_cell().canvas()
H.drag(app, c, H.pt(c,0.3,0.3), H.pt(c,0.5,0.3)); n = c.mask_pixels()
dock._tool_btns["rect"].setChecked(True); dock._apply_tool()
H.drag(app, c, H.pt(c,0.2,0.2), H.pt(c,0.7,0.7)); r1 = c.crop_rect()
dock._clear_btn.click(); app.processEvents()
check("Clear wipes mask and rect", c.mask_pixels() == 0 and c.crop_rect() is None)
dock._undo_btn.click(); app.processEvents()
check("Undo after Clear restores the mask", c.mask_pixels() == n, str(c.mask_pixels()))
check("Undo after Clear also restores the rectangle (README: undo steps back through clears)", c.crop_rect() == r1, f"rect after undo: {c.crop_rect()}")
# second rect replaces first; undo?
H.drag(app, c, H.pt(c,0.1,0.1), H.pt(c,0.4,0.4)); r2 = c.crop_rect()
dock._undo_btn.click(); app.processEvents()
print("after undo following rect replace: rect", c.crop_rect(), "mask", c.mask_pixels(), "status", dock._status_lbl.text())
check("Undo after replacing the rect does not silently pop a MASK state instead", c.mask_pixels() == n, f"mask {c.mask_pixels()} (was {n}), rect {c.crop_rect()}")
# undo depth: 12 strokes then undo 12 → only 10 possible
c.clear_annotations(); dock._tool_btns["paint"].setChecked(True); dock._apply_tool()
for i in range(12):
    H.click(c, H.pt(c, 0.1 + i*0.05, 0.5))
k = 0
while c.undo_annotation(): k += 1
check("undo depth is 10", k == 10, str(k))
win.close(); app.processEvents(); sys.exit(summary())
