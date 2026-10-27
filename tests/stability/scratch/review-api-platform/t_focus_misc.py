"""Ctrl+Z after clicking the brush spin box arrows; shortcuts while the dock is floating."""
import os, sys, shutil
from common import *
import harness as H
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QStyle, QStyleOptionSpinBox
app, win = H.boot()
D = os.path.join(SCR, "data", "ws_focus"); shutil.rmtree(D, ignore_errors=True); os.makedirs(D)
for f in sorted(os.listdir(FIX))[:3]: shutil.copy(os.path.join(FIX, f), D)
ws = H.open_workspace(app, win, D)
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.5, 0.2)); n1 = canvas.mask_pixels()
check("stroke", n1 > 0)
# click the spin box's up arrow with the mouse (what a user does to grow the brush), then Ctrl+Z
sp = dock._brush_spin
opt = QStyleOptionSpinBox(); sp.initStyleOption(opt)
up = sp.style().subControlRect(QStyle.CC_SpinBox, opt, QStyle.SC_SpinBoxUp, sp)
QTest.mouseClick(sp, Qt.LeftButton, Qt.NoModifier, up.center()); app.processEvents()
print("spin value after arrow click:", sp.value(), "focus:", type(app.focusWidget()).__name__)
QTest.keyClick(app.focusWidget(), Qt.Key_Z, Qt.ControlModifier); app.processEvents()
print("after Ctrl+Z: spin", sp.value(), "mask", canvas.mask_pixels(), "status:", dock._status_lbl.text())
check("Ctrl+Z after clicking the spin arrow undoes the MASK stroke", canvas.mask_pixels() == 0, f"mask={canvas.mask_pixels()} (stroke {n1}), spin={sp.value()}")
# W/L spin in the toolbar, same question
canvas.setFocus(); app.processEvents()
if canvas.mask_pixels() == 0:
    H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.5, 0.2)); n1 = canvas.mask_pixels()
win._ww_spin.setFocus(); app.processEvents()
QTest.keyClick(win._ww_spin, Qt.Key_Z, Qt.ControlModifier); app.processEvents()
check("Ctrl+Z with the toolbar W spin focused undoes the mask", canvas.mask_pixels() == 0, f"mask={canvas.mask_pixels()}")

# ── floating dock ───────────────────────────────────────────────────────────
canvas.setFocus(); app.processEvents()
if canvas.mask_pixels() == 0:
    H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.5, 0.2)); n1 = canvas.mask_pixels()
dock.setFloating(True); app.processEvents(); dock.activateWindow(); dock._list.setFocus(); app.processEvents()
print("floating:", dock.isFloating(), "visible:", dock.isVisible(), "activeWindow is dock:", app.activeWindow() is dock, "canvas mode:", canvas.wl_mode())
check("floating dock keeps the tool active on the canvas", canvas.wl_mode() == "paint", canvas.wl_mode())
QTest.keyClick(dock._list, Qt.Key_Z, Qt.ControlModifier); app.processEvents()
check("Ctrl+Z with the floating dock focused undoes the mask", canvas.mask_pixels() == 0, f"mask={canvas.mask_pixels()} (stroke {n1})")
saves = []; orig = dock._save; dock._save = lambda advance: saves.append(advance)
QTest.keyClick(dock._list, Qt.Key_S, Qt.ControlModifier); app.processEvents()
check("Ctrl+S with the floating dock focused triggers save", saves == [True], str(saves))
dock._save = orig
QTest.keyClick(dock._list, Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier); app.processEvents()
check("Ctrl+Shift+W with the floating dock focused hides it", not dock.isVisible(), str(dock.isVisible()))
dock.setFloating(False); win._ws_btn.setChecked(True); app.processEvents()
# dock closed via its title-bar close button (QDockWidget.close) → button unchecked, tools reset
dock.close(); app.processEvents()
check("closing the dock unchecks Workspace button and restores drag", not win._ws_btn.isChecked() and canvas.wl_mode() == "drag", f"{win._ws_btn.isChecked()} {canvas.wl_mode()}")
win.close(); app.processEvents()
sys.exit(summary())
