"""Minimal repro: with the dock open (Brush checked), loading a file from the study tree into the active panel leaves the canvas in 'drag' mode."""
from common import *
from viewer_vidi.tree_panel import _make_series_meta
app, win = H.boot(); dock, quad = win._dock, win._quad
ws = H.open_workspace(app, win, fresh_ws("p21", [os.path.join(FIX, "bpd1_20100101_1.dcm")]))
cell = quad.active_cell(); c = cell.canvas()
check("after workspace open: Brush checked and canvas in paint", dock._tool_btns["paint"].isChecked() and c.wl_mode() == "paint")
win._on_series_selected(_make_series_meta(os.path.join(FIX, "bpd1_20100101_2.dcm")))   # same path as a tree double-click
H.wait_loaded(app, cell)
print("tool buttons checked:", [m for m, b in dock._tool_btns.items() if b.isChecked()], "canvas mode:", c.wl_mode())
check("canvas mode still matches the checked tool after a tree load", c.wl_mode() == "paint", c.wl_mode())
wc0 = c.wl(); H.drag(app, c, H.pt(c, 0.3, 0.3), H.pt(c, 0.6, 0.3))
print("after a 'brush' drag: mask px", c.mask_pixels(), "wl before/after", wc0, c.wl())
check("a drag paints instead of changing W/L", c.mask_pixels() > 0 and c.wl() == wc0)
win.close(); app.processEvents(); sys.exit(summary())
