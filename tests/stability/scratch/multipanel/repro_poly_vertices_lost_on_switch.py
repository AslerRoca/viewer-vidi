"""Repro: an in-progress polygon (vertices clicked, not yet closed) on panel A is discarded when the user
clicks another panel and then clicks back on A. The activating press on A fires active_cell_changed →
AnnotationDock._apply_tool() → canvas.set_wl_mode('poly'), which resets _poly_pts even though the mode did
not change; A's press then starts a NEW polygon with one vertex.
Expected: the 3 vertices survive (tool unchanged) and the click adds a 4th. Observed: 1 vertex."""
import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB)
import harness as H
app, win = H.boot()
dock, quad = win._dock, win._quad
c0, c1 = quad.cell_at(0), quad.cell_at(1); cv0, cv1 = c0.canvas(), c1.canvas()
ws = H.open_workspace(app, win, STAB + "/multipanel/ws"); H.wait_loaded(app, c0)
c1.activated.emit(); app.processEvents(); H.load_file(app, c1, ws.items[1].path)
c0.activated.emit(); app.processEvents()
dock._tool_btns["poly"].setChecked(True); dock._apply_tool()
for p in (H.pt(cv0, .2, .2), H.pt(cv0, .4, .2), H.pt(cv0, .4, .4)):
    H.click(cv0, p)
print("cell0 vertices:", cv0._poly_pts)
H.click(cv1, H.pt(cv1, .5, .5)); app.processEvents()           # user clicks panel B
print("after click on cell1 → active:", quad.cells().index(quad.active_cell()), "| cell0 vertices:", cv0._poly_pts, "| cell0 mode:", cv0.wl_mode())
H.click(cv0, H.pt(cv0, .2, .4)); app.processEvents()           # user clicks back on panel A (4th vertex)
print("after click back on cell0 → active:", quad.cells().index(quad.active_cell()), "| cell0 vertices:", cv0._poly_pts, "(expected 4)")
win.close(); app.processEvents()
