"""_mask_nonempty must be True whenever mask.any() (else the overlay is invisible while a mask exists)."""
from common import *
import numpy as np, random
from PyQt5.QtCore import Qt
app, win = H.boot(); dock, quad = win._dock, win._quad
ws = H.open_workspace(app, win, fresh_ws("p16", [os.path.join(FIX, "bpd1_20100101_1.dcm")]))
c = quad.active_cell().canvas(); rng = random.Random(1)
dock._brush_spin.setValue(40)
viol = []
for step in range(300):
    op = rng.choice(["paint", "erase", "polyfill", "polyerase", "undo", "clear", "rect"])
    if op in ("paint", "erase"):
        dock._tool_btns["paint"].setChecked(True); dock._apply_tool(); dock._erase_chk.setChecked(op == "erase")
        H.drag(app, c, H.pt(c, rng.random(), rng.random()), H.pt(c, rng.random(), rng.random()), steps=3)
    elif op in ("polyfill", "polyerase"):
        dock._erase_chk.setChecked(op == "polyerase"); dock._tool_btns["poly"].setChecked(True); dock._apply_tool()
        for _ in range(3): H.click(c, H.pt(c, rng.random(), rng.random()))
        H.key(c, Qt.Key_Return)
    elif op == "undo": c.undo_annotation()
    elif op == "clear": c.clear_annotations()
    else:
        dock._tool_btns["rect"].setChecked(True); dock._apply_tool()
        H.drag(app, c, H.pt(c, rng.random(), rng.random()), H.pt(c, rng.random(), rng.random()), steps=3)
    app.processEvents()
    anyp = bool(c.mask().any())
    if anyp and not c._mask_nonempty: viol.append((step, op, "mask has pixels but overlay flag False"))
    inv = H.invariants(c)
    if inv: viol.append((step, op, inv))
check("300 random ops: overlay flag and invariants hold", not viol, str(viol[:5]))
win.close(); app.processEvents(); sys.exit(summary())
