from common import *
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QMessageBox
app, win = H.boot(); dock, quad = win._dock, win._quad
ws = H.open_workspace(app, win, fresh_ws("ctrls"), "image")
canvas = quad.active_cell().canvas()
QTest.keyClick(win, Qt.Key_S, Qt.ControlModifier); app.processEvents()
print("Ctrl+S with nothing drawn -> status:", repr(dock._status_lbl.text()), "index", dock._index)
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.6, 0.3))
QTest.keyClick(win, Qt.Key_S, Qt.ControlModifier); app.processEvents()
print("Ctrl+S with a stroke     -> status:", repr(dock._status_lbl.text()), "index", dock._index, "done0", ws.items[0].done)
H.wait_loaded(app, quad.active_cell())
QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier); app.processEvents()
print("Ctrl+Z on fresh item      -> status:", repr(dock._status_lbl.text()))
win.close(); app.processEvents()
