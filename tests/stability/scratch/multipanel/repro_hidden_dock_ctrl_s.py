"""Repro: Ctrl+S (save_and_next) still works while the Workspace dock is HIDDEN. It saves, advances, and
_load_index re-applies the dock's tool to the active panel — so the panel ends up in 'paint' mode while
the dock is closed, although hiding the dock is documented to restore ordinary W/L drag.
Expected: either Ctrl+S is inert while the dock is hidden, or the panel stays in 'drag'.
Observed: item saved + advanced, canvas mode 'paint' with the dock hidden; the next left-drag paints."""
import os, sys, shutil
os.environ["QT_QPA_PLATFORM"] = "offscreen"
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB)
import harness as H
from PyQt5.QtCore import Qt
app, win = H.boot()
dock, quad = win._dock, win._quad
c0 = quad.cell_at(0); cv0 = c0.canvas()
WS = STAB + "/multipanel/ws_hidden"
shutil.rmtree(WS, ignore_errors=True); shutil.copytree(STAB + "/multipanel/ws", WS)
ws = H.open_workspace(app, win, WS); H.wait_loaded(app, c0)
H.drag(app, cv0, H.pt(cv0, .3, .3), H.pt(cv0, .6, .3))
print("mask px before hide:", cv0.mask_pixels(), "| index", dock._index)
win._ws_btn.setChecked(False); app.processEvents()
print("dock visible:", dock.isVisible(), "| canvas mode after hide:", cv0.wl_mode())
app.setActiveWindow(win); H.key(win, Qt.Key_S, Qt.ControlModifier); app.processEvents(); H.wait_loaded(app, c0)
print("after Ctrl+S with dock hidden → status:", repr(dock._status_lbl.text()), "| index", dock._index,
      "| done:", [it.done for it in dock._ws.items])
print("dock visible:", dock.isVisible(), "| canvas mode:", cv0.wl_mode())
wl0 = cv0.wl(); H.drag(app, cv0, H.pt(cv0, .3, .3), H.pt(cv0, .6, .3))
print("left-drag with dock hidden: mask px", cv0.mask_pixels(), "| W/L", wl0, "→", cv0.wl())
win.close(); app.processEvents()
