"""Probe: do QShortcuts fire under QTest.keyClick offscreen? Do overlay hit-rects refresh on processEvents?"""
import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB)
import harness as H
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
app, win = H.boot()
dock, quad = win._dock, win._quad
c0 = quad.cell_at(0); cv0 = c0.canvas()
print("activeWindow before:", app.activeWindow())
H.key(win, Qt.Key_I, Qt.ControlModifier); app.processEvents()
print("Ctrl+I on win (no activation):", win._invert_btn.isChecked())
win.activateWindow(); app.setActiveWindow(win); app.processEvents()
print("activeWindow after:", app.activeWindow() is win)
H.key(win, Qt.Key_I, Qt.ControlModifier); app.processEvents()
print("Ctrl+I on win (after setActiveWindow):", win._invert_btn.isChecked())
H.key(cv0, Qt.Key_I, Qt.ControlModifier); app.processEvents()
print("Ctrl+I on canvas:", win._invert_btn.isChecked())
H.key(win, Qt.Key_B, Qt.ControlModifier); app.processEvents()
print("Ctrl+B tree hidden:", not win._tree.isVisible())
H.key(win, Qt.Key_B, Qt.ControlModifier); app.processEvents()
H.key(win, Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier); app.processEvents()
print("Ctrl+Shift+W dock visible:", dock.isVisible())

# overlay hit-rect refresh
ws = H.open_workspace(app, win, STAB + "/multipanel/ws")
H.wait_loaded(app, c0)
c0._info_btn.setChecked(True); app.processEvents()
print("rects after processEvents only:", len(cv0._ov_header_rects))
H.pump(app, 100)
print("rects after pump 100ms:", len(cv0._ov_header_rects))
cv0.repaint(); print("rects after repaint():", len(cv0._ov_header_rects))
r, title = cv0._ov_header_rects[0]
y_before = r.y()
H.click(cv0, r.center()); app.processEvents()
print("expanded:", title in cv0._ov_expanded, "rect y after processEvents:", [rr.y() for rr, t in cv0._ov_header_rects if t == title], "(before", y_before, ")")
H.pump(app, 100)
print("rect y after pump:", [rr.y() for rr, t in cv0._ov_header_rects if t == title])
win.close(); app.processEvents()
