"""Boot the app with the stylesheet, open the dock + a workspace, touch every widget, and let stderr show
any 'Unknown property' / 'Could not parse' / 'Ambiguous shortcut' warnings."""
import os, sys, shutil
from common import *
import harness as H
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
app, win = H.boot()
D = os.path.join(SCR, "data", "ws_style"); shutil.rmtree(D, ignore_errors=True); os.makedirs(D)
for f in sorted(os.listdir(FIX))[:2]: shutil.copy(os.path.join(FIX, f), D)
ws = H.open_workspace(app, win, D)
dock = win._dock
check("stylesheet applied (non-empty)", len(win.styleSheet()) > 1000)
check("dock visible with workspace", dock.isVisible() and len(ws.items) == 2)
for b in dock._tool_btns.values(): b.click(); app.processEvents()
for c in list(dock._fmt_chk.values()) + [dock._mask_chk, dock._crop_chk, dock._image_chk, dock._erase_chk]:
    c.toggle(); app.processEvents(); c.toggle(); app.processEvents()
dock._list.setCurrentRow(1); app.processEvents()
dock._brush_spin.setValue(7); app.processEvents()
pm = dock.grab(); check("dock renders", not pm.isNull(), f"{pm.width()}x{pm.height()}")
# shortcuts: Ctrl+Z / Ctrl+S / Ctrl+Shift+W via the window (ambiguity would print a warning)
QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier); app.processEvents()
QTest.keyClick(win, Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier); app.processEvents()
check("Ctrl+Shift+W hides the dock", not dock.isVisible())
QTest.keyClick(win, Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier); app.processEvents()
check("Ctrl+Shift+W shows it again", dock.isVisible())
win.close(); app.processEvents()
sys.exit(summary())
