"""Enter / Esc reach the canvas only if it has keyboard focus after a click (ClickFocus); send keys to the focus widget, not the canvas."""
from common import *
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
app, win = H.boot(); dock, quad = win._dock, win._quad
win.activateWindow()
ws = H.open_workspace(app, win, fresh_ws("p09", [os.path.join(FIX, "bpd1_20100101_1.dcm")]))
c = quad.active_cell().canvas()
dock._tool_btns["poly"].setChecked(True); dock._apply_tool()
for f in ((0.2,0.2),(0.5,0.2),(0.5,0.5)):
    QTest.mouseClick(c, Qt.LeftButton, Qt.NoModifier, H.pt(c, *f))
app.processEvents()
fw = app.focusWidget()
print("focus widget after clicks:", type(fw).__name__ if fw else None)
check("canvas has keyboard focus after clicking vertices", fw is c)
QTest.keyClick(fw or win, Qt.Key_Return); app.processEvents()
check("Enter (to focus widget) fills the polygon", c.mask_pixels() > 0, str(c.mask_pixels()))
# Esc cancels
for f in ((0.6,0.6),(0.8,0.6),(0.8,0.8)):
    QTest.mouseClick(c, Qt.LeftButton, Qt.NoModifier, H.pt(c, *f))
check("3 vertices pending", len(c._poly_pts) == 3)
QTest.keyClick(app.focusWidget() or win, Qt.Key_Escape); app.processEvents()
check("Esc cancels pending polygon", c._poly_pts == [])
# right-click drops last vertex
for f in ((0.6,0.6),(0.8,0.6),(0.8,0.8)):
    QTest.mouseClick(c, Qt.LeftButton, Qt.NoModifier, H.pt(c, *f))
H.click(c, H.pt(c, 0.85, 0.85), Qt.RightButton); app.processEvents()
check("right-click drops last vertex", len(c._poly_pts) == 2, str(len(c._poly_pts)))
# Space / I keys consumed by the cell filter still (no crash)
QTest.keyClick(c, Qt.Key_I); QTest.keyClick(c, Qt.Key_Space); app.processEvents()
check("I / Space while in poly mode do not crash", True)
# window-level shortcuts
dock._tool_btns["paint"].setChecked(True); dock._apply_tool(); c.clear_annotations()
H.click(c, H.pt(c, 0.5, 0.5)); n = c.mask_pixels()
QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier); app.processEvents()
check("Ctrl+Z on the window undoes the stroke", c.mask_pixels() == 0, str(c.mask_pixels()))
QTest.keyClick(win, Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier); app.processEvents()
check("Ctrl+Shift+W hides dock and restores drag", not dock.isVisible() and c.wl_mode() == "drag", c.wl_mode())
QTest.keyClick(win, Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier); app.processEvents()
check("Ctrl+Shift+W again shows dock, tool re-applied", dock.isVisible() and c.wl_mode() == "paint", c.wl_mode())
H.click(c, H.pt(c, 0.5, 0.5))
QTest.keyClick(win, Qt.Key_S, Qt.ControlModifier); app.processEvents()
check("Ctrl+S saves (status) and marks done", ws.items[0].done and dock._status_lbl.text().startswith("Saved"), dock._status_lbl.text())
win.close(); app.processEvents(); sys.exit(summary())
