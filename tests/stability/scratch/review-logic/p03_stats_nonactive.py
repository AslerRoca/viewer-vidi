"""annotation_changed from a NON-active canvas → dock._refresh_stats reads the active one; plus empty-panel Save message."""
from common import *
import numpy as np
from PyQt5.QtCore import Qt
app, win = H.boot()
dock, quad = win._dock, win._quad
cells = quad.cells(); c0, c1 = cells[0], cells[1]
ws = H.open_workspace(app, win, fresh_ws("p03", [os.path.join(FIX, "bpd1_20100101_1.dcm"), os.path.join(FIX, "bpd1_20100101_2.dcm")]))
canvas0 = c0.canvas()
# paint in cell 0
H.drag(app, canvas0, H.pt(canvas0, 0.3, 0.3), H.pt(canvas0, 0.5, 0.3))
n0 = canvas0.mask_pixels()
check("stats label shows cell0 mask count", f"mask {n0:,} px" in dock._stats_lbl.text(), dock._stats_lbl.text())
# activate cell 1 (empty) programmatically, as a click in it would
quad._on_activated(c1); app.processEvents()
check("cell1 became active and got the paint tool", quad.active_cell() is c1 and c1.canvas().wl_mode() == "paint")
check("stats label refreshed for the (empty) active cell", dock._stats_lbl.text().startswith("mask 0 px"), dock._stats_lbl.text())
check("cell0 keeps its paint mode after losing activation (not restored to drag)", canvas0.wl_mode() == "paint", canvas0.wl_mode())
# now a programmatic change on the NON-active canvas 0 (clear_annotations via API, e.g. a stray Undo) → signal → stats read active (cell1)
canvas0.clear_annotations(); app.processEvents()
check("non-active canvas change leaves stats showing the active cell", dock._stats_lbl.text().startswith("mask 0 px"), dock._stats_lbl.text())
# Save with the empty active panel: message
dock._save(advance=False); app.processEvents()
msg = dock._status_lbl.text()
print("status after Save on empty active panel:", repr(msg))
check("Save with an EMPTY active panel does not claim 'still loading'", "loading" not in msg.lower(), msg)
# keyboard Enter on non-active canvas in poly mode
dock._tool_btns["poly"].setChecked(True); dock._apply_tool()
canvas0.set_wl_mode("poly")
for f in ((0.2,0.2),(0.4,0.2),(0.4,0.4)):
    H.click(canvas0, H.pt(canvas0, *f))
check("clicking in cell0 re-activates it", quad.active_cell() is c0)
H.key(canvas0, Qt.Key_Return); app.processEvents()
check("Enter fills polygon on cell0 and stats follow", canvas0.mask_pixels() > 0 and f"mask {canvas0.mask_pixels():,} px" in dock._stats_lbl.text(), dock._stats_lbl.text())
win.close(); app.processEvents()
sys.exit(summary())
