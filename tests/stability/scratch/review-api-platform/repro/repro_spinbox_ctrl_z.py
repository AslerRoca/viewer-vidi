"""REPRO: after the user clicks the Brush-px spin box arrow (or focuses any QSpinBox/QDoubleSpinBox),
Ctrl+Z is consumed by the spin box's internal QLineEdit (QWidgetLineControl accepts the Undo
ShortcutOverride unconditionally), so the window-level Ctrl+Z mask-undo silently does nothing.
Run: QT_QPA_PLATFORM=offscreen timeout 300 ~/miniconda3/envs/viewer_vidi/bin/python repro_spinbox_ctrl_z.py"""
import os, sys, shutil
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QStyle, QStyleOptionSpinBox
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out_spin"); shutil.rmtree(D, ignore_errors=True); os.makedirs(D)
shutil.copy(os.path.join(H.FIXTURES, sorted(os.listdir(H.FIXTURES))[0]), D)
app, win = H.boot(); H.open_workspace(app, win, D)
dock, canvas = win._dock, win._quad.active_cell().canvas()
H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.5, 0.2)); n = canvas.mask_pixels()
sp = dock._brush_spin; opt = QStyleOptionSpinBox(); sp.initStyleOption(opt)
QTest.mouseClick(sp, Qt.LeftButton, Qt.NoModifier, sp.style().subControlRect(QStyle.CC_SpinBox, opt, QStyle.SC_SpinBoxUp, sp).center()); app.processEvents()
QTest.keyClick(app.focusWidget(), Qt.Key_Z, Qt.ControlModifier); app.processEvents()
print(f"stroke {n} px; focus={type(app.focusWidget()).__name__}; after Ctrl+Z mask={canvas.mask_pixels()} (expected 0), status='{dock._status_lbl.text()}'")
dock._list.setFocus(); QTest.keyClick(dock._list, Qt.Key_Z, Qt.ControlModifier); app.processEvents()
print(f"same Ctrl+Z with the list focused: mask={canvas.mask_pixels()}")
win.close()
