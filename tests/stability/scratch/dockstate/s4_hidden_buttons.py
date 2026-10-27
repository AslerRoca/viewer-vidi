"""Clear/Undo button clicks and tool buttons while the dock is hidden (programmatic): crash check only."""
import os, sys
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/dockstate")
from common import *
app, win = H.boot()
dock, quad = win._dock, win._quad; cell = quad.active_cell(); canvas = cell.canvas()
ws = H.open_workspace(app, win, fresh_ws("S4", n=2)); stroke(app, canvas); n = canvas.mask_pixels()
win._ws_btn.setChecked(False); app.processEvents()
dock._undo_btn.click(); app.processEvents()
check("hidden: Undo button click -> dock.undo() guarded, mask unchanged", canvas.mask_pixels() == n)
dock._clear_btn.click(); app.processEvents()
check("hidden: Clear button click wipes the mask (no visibility guard) — programmatic only, no crash", canvas.mask_pixels() == 0 and not H.invariants(canvas))
dock._tool_btns["poly"].click(); app.processEvents()
check("hidden: tool button click switches the hidden-dock canvas into poly (no guard) — programmatic only", canvas.wl_mode() == "poly", canvas.wl_mode())
win._ws_btn.setChecked(True); app.processEvents()
check("show: poly applied", canvas.wl_mode() == "poly")
win._ws_btn.setChecked(False); app.processEvents()
check("hide: back to drag", canvas.wl_mode() == "drag")
# toggle the dock 20 times quickly with a stroke in between: invariants
for i in range(20):
    win._ws_btn.toggle(); app.processEvents()
    if dock.isVisible(): dock._tool_btns["paint"].click(); stroke(app, canvas)
check("20 rapid toggles with strokes: invariants hold, mode consistent with visibility",
      not H.invariants(canvas) and (canvas.wl_mode() == ("paint" if dock.isVisible() else "drag")), f"{dock.isVisible()} {canvas.wl_mode()}")
win.close(); app.processEvents(); sys.exit(1 if summary() else 0)
