"""REPRO: Ctrl+S (save_and_next) is not guarded by dock visibility. With the dock hidden
it saves and advances, and _load_index() -> _apply_tool() puts the active panel into
'paint' mode although the dock is hidden (README: hiding the dock restores W/L drag)."""
import os, sys
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/dockstate")
from common import *
from PyQt5.QtCore import Qt
app, win = H.boot(); win.activateWindow(); app.processEvents()
dock, quad = win._dock, win._quad; cell = quad.active_cell(); canvas = cell.canvas()
ws = H.open_workspace(app, win, fresh_ws("R1", n=3))
stroke(app, canvas)                                   # paint something on item 0
win._ws_btn.setChecked(False); app.processEvents()    # hide the dock -> drag mode (documented)
print("dock visible:", dock.isVisible(), "| mode after hide:", canvas.wl_mode())
H.key(win, Qt.Key_S, Qt.ControlModifier); H.wait_loaded(app, cell)
mode = canvas.wl_mode()
wl0 = canvas.wl(); H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.6, 0.6))
print(f"after Ctrl+S with dock hidden: item0 done={ws.items[0].done} index={dock._index} dock visible={dock.isVisible()}")
print(f"OBSERVED: active canvas mode = {mode!r}; a left-drag painted {canvas.mask_pixels()} mask px, W/L {wl0} -> {canvas.wl()}")
print("EXPECTED: dock hidden => Ctrl+S ignored like Ctrl+Z, or the loaded item stays in 'drag' mode")
win.close(); app.processEvents()
sys.exit(1 if mode != "drag" else 0)
