"""Repro: with the Workspace dock open and Brush selected, loading a series into the ACTIVE panel through
the pre-existing paths (left tree double-click → MainWindow._on_series_selected, or drag-drop →
ViewCell.dropEvent) leaves that panel's canvas in W/L 'drag' mode while the dock still shows Brush.
The dock's own loader (_load_index) re-applies the tool after load_meta; these two paths do not.
Expected: canvas.wl_mode() == dock tool ('paint'). Observed: 'drag' → the next left-drag changes W/L instead of painting."""
import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB)
import harness as H
app, win = H.boot()
from viewer_vidi.tree_panel import _make_series_meta
dock, quad = win._dock, win._quad
c0 = quad.cell_at(0); cv0 = c0.canvas()
ws = H.open_workspace(app, win, STAB + "/multipanel/ws"); H.wait_loaded(app, c0)
print("dock tool:", dock._current_tool(), "| canvas mode after dock load:", cv0.wl_mode())

meta = _make_series_meta(ws.items[2].path)
win._on_series_selected(meta)                 # == left tree double-click (tree.series_selected)
H.wait_loaded(app, c0)
print("TREE path  → dock tool:", dock._current_tool(), "| canvas mode:", cv0.wl_mode())
wl0 = cv0.wl(); H.drag(app, cv0, H.pt(cv0, .3, .3), H.pt(cv0, .6, .3))
print("  left-drag now: W/L", wl0, "→", cv0.wl(), "| mask px:", cv0.mask_pixels())

dock._tool_btns["paint"].setChecked(True); dock._apply_tool()
c0.load_meta(meta); c0.activated.emit()       # == ViewCell.dropEvent onto the already-active panel
H.wait_loaded(app, c0)
print("DROP path  → dock tool:", dock._current_tool(), "| canvas mode:", cv0.wl_mode())
win.close(); app.processEvents()
