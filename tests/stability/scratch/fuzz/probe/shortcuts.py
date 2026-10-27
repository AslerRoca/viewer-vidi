import sys, os
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
app, win = H.boot()
dock = win._dock
print("active window:", app.activeWindow() is win, "dock visible:", dock.isVisible())
QTest.keyClick(win, Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier); app.processEvents()
print("after Ctrl+Shift+W on win: dock visible:", dock.isVisible(), "ws_btn:", win._ws_btn.isChecked())
QTest.keyClick(win._quad.active_cell().canvas(), Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier); app.processEvents()
print("after Ctrl+Shift+W on canvas: dock visible:", dock.isVisible())
QTest.keyClick(win, Qt.Key_I, Qt.ControlModifier); app.processEvents()
print("after Ctrl+I: invert btn", win._invert_btn.isChecked())
win.close(); app.processEvents()
