"""Loading a series from the study tree while the Workspace dock is open silently
reverts the active panel to W/L drag although the dock still shows Brush selected."""
from common import *
from viewer_vidi.tree_panel import _make_series_meta
app, win = H.boot(); dock, quad = win._dock, win._quad
ws = H.open_workspace(app, win, fresh_ws("tree"), "image")
cell = quad.active_cell(); canvas = cell.canvas()
print("after opening workspace: dock tool =", dock._current_tool(), "canvas mode =", canvas.wl_mode())
# the real tree path: StudyTreeWidget.series_selected -> MainWindow._on_series_selected
meta = _make_series_meta(os.path.join(H.FIXTURES, "bpd3_20100502_1.dcm"))
win._on_series_selected(meta); H.wait_loaded(app, cell)
print("after tree load:         dock tool =", dock._current_tool(), "canvas mode =", canvas.wl_mode(),
      "Brush button checked =", dock._tool_btns["paint"].isChecked(), "dock visible =", dock.isVisible())
wl0 = canvas.wl()
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.6, 0.3))
print("brush drag -> mask_pixels =", canvas.mask_pixels(), " W/L changed:", canvas.wl() != wl0, wl0, "->", canvas.wl())
ok = canvas.wl_mode() == "paint" and canvas.mask_pixels() > 0
print("RESULT:", "PASS" if ok else "FAIL (expected mode 'paint' and a painted stroke)")
win.close(); app.processEvents(); sys.exit(0 if ok else 1)
