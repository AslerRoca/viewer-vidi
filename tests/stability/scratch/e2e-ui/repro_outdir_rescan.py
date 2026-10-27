"""Output dir with a path separator ('sub/out'): on reopen its PNG exports become job items."""
import os, sys
import repro_common as R
from repro_common import H
from PyQt5.QtTest import QTest
ws_dir = R.fresh_ws("repro_outdir", ["bpd3_20100419_5.dcm"])
app, win = H.boot(); dock = win._dock
win._ws_btn.setChecked(True); app.processEvents()
R.open_dir(app, win, ws_dir)
canvas = win._quad.active_cell().canvas()
dock._out_edit.selectAll(); QTest.keyClicks(dock._out_edit, "sub/out"); app.processEvents()
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.5, 0.3))
QTest.mouseClick(dock._save_btn, 1); app.processEvents()
print("status:", dock._status_lbl.text())
R.open_dir(app, win, ws_dir)                      # Open directory… again, same dir, same Output dir field
items = [os.path.relpath(it.path, ws_dir) for it in dock.workspace().items]
print("items after reopen:", items)
win.close(); sys.exit(0 if len(items) == 1 else 1)
