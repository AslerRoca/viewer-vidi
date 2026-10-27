"""Ctrl+S with the Workspace dock hidden: saves, advances, swaps the panel image and leaves paint mode on."""
import os, sys
import repro_common as R
from repro_common import H
from PyQt5.QtCore import Qt
ws_dir = R.fresh_ws("repro_hidden", ["bpd1_20100101_1.dcm", "bpd1_20100101_2.dcm"])
app, win = H.boot(); dock = win._dock; cell = win._quad.active_cell(); canvas = cell.canvas()
win._ws_btn.setChecked(True); app.processEvents()
R.open_dir(app, win, ws_dir); ws = dock.workspace()
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.5, 0.3))
R.ctrl(app, win, win, Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier)        # hide the dock
print("dock visible:", dock.isVisible(), "| canvas mode:", canvas.wl_mode())
R.ctrl(app, win, canvas, Qt.Key_S)                                             # Ctrl+S while hidden
H.wait_loaded(app, cell)
print("item1 done:", ws.items[0].done, "| index:", dock._index, "| panel shows:", os.path.basename(cell.series_data().meta.series_dir),
      "| canvas mode while dock hidden:", canvas.wl_mode(), "| files:", sorted(os.listdir(os.path.join(ws_dir, "vidi_output", "png"))) if os.path.isdir(os.path.join(ws_dir, "vidi_output", "png")) else None)
bad = ws.items[0].done or dock._index != 0 or canvas.wl_mode() != "drag"
win.close(); sys.exit(1 if bad else 0)
