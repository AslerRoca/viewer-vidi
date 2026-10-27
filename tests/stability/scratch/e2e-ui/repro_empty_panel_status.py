"""Ctrl+S with an EMPTY active panel reports 'Image still loading — try again in a moment.'"""
import sys
import repro_common as R
from repro_common import H
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
ws_dir = R.fresh_ws("repro_empty", ["bpd1_20100107_1.dcm"])
app, win = H.boot(); dock = win._dock; quad = win._quad
win._ws_btn.setChecked(True); app.processEvents()
R.open_dir(app, win, ws_dir)
cell2 = quad.cells()[1]
QTest.mouseClick(cell2, Qt.LeftButton); app.processEvents()           # click the empty panel 2 → active
print("active panel:", quad.cells().index(quad.active_cell()), "| has data:", cell2.series_data() is not None)
R.ctrl(app, win, cell2, Qt.Key_S)
print("status after Ctrl+S:", repr(dock._status_lbl.text()))
win.close(); sys.exit(0)
