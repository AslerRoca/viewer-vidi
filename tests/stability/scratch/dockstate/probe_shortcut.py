"""Probe: do QShortcuts fire via QTest.keyClick(win, ...) offscreen?"""
import os, sys
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/dockstate")
from common import *
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
app, win = H.boot()
dock, quad = win._dock, win._quad
win.activateWindow(); app.processEvents()
print("activeWindow is win:", QApplication.activeWindow() is win)
print("dock visible before:", dock.isVisible())
H.key(win, Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier); app.processEvents()
print("dock visible after Ctrl+Shift+W:", dock.isVisible(), "ws_btn checked:", win._ws_btn.isChecked())
H.key(win, Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier); app.processEvents()
print("dock visible after 2nd Ctrl+Shift+W:", dock.isVisible(), "ws_btn checked:", win._ws_btn.isChecked())
# try sending to a child (canvas)
canvas = quad.active_cell().canvas()
H.key(canvas, Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier); app.processEvents()
print("dock visible after Ctrl+Shift+W sent to canvas:", dock.isVisible())
win.close(); app.processEvents()
