"""Save with an empty (never loaded) panel active reports 'Image still loading'."""
from common import *
app, win = H.boot(); dock, quad = win._dock, win._quad
ws = H.open_workspace(app, win, fresh_ws("empty"), "image")
cells = quad.cells()
print("active cell:", cells.index(quad.active_cell()), "| cell 1 series_data:", cells[1].series_data())
H.click(cells[1].canvas(), H.pt(cells[1].canvas(), 0.5, 0.5)); app.processEvents()
print("after clicking panel 1: active cell =", cells.index(quad.active_cell()))
dock._save(advance=False); app.processEvents()
print("Save status:", repr(dock._status_lbl.text()))
H.pump(app, 1500)
dock._save(advance=False); app.processEvents()
print("Save status after 1.5 s:", repr(dock._status_lbl.text()))
win.close(); app.processEvents()
