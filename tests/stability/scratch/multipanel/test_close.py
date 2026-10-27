"""Close the main window with the dock open and (a) a brush stroke in progress, (b) a polygon in progress,
(c) a load in flight in another cell. Expect a clean exit and no stderr noise. Variant chosen by argv[1]."""
import os, sys, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB)
import harness as H
from PyQt5.QtCore import Qt
variant = sys.argv[1] if len(sys.argv) > 1 else "stroke"
app, win = H.boot()
dock, quad = win._dock, win._quad
c0, c1 = quad.cell_at(0), quad.cell_at(1)
cv0, cv1 = c0.canvas(), c1.canvas()
ws = H.open_workspace(app, win, STAB + "/multipanel/ws")
H.wait_loaded(app, c0)
if variant == "stroke":
    H.press(cv0, H.pt(cv0, .3, .3)); H.move(cv0, H.pt(cv0, .4, .3), Qt.LeftButton); app.processEvents()
    print("stroke in progress:", cv0._stroke_last is not None, "mask px", cv0.mask_pixels())
elif variant == "poly":
    dock._tool_btns["poly"].setChecked(True); dock._apply_tool()
    for p in (H.pt(cv0, .2, .2), H.pt(cv0, .4, .2), H.pt(cv0, .4, .4)):
        H.click(cv0, p)
    print("poly in progress:", len(cv0._poly_pts))
elif variant == "rect":
    dock._tool_btns["rect"].setChecked(True); dock._apply_tool()
    H.press(cv0, H.pt(cv0, .3, .3)); H.move(cv0, H.pt(cv0, .6, .6), Qt.LeftButton); app.processEvents()
    print("rect drag in progress:", cv0._rect_start is not None)
elif variant == "loading":
    c1.activated.emit(); app.processEvents()
    from viewer_vidi.tree_panel import _make_series_meta
    c1.load_meta(_make_series_meta(STAB + "/multipanel/mr3d"))   # do not wait
    H.press(cv0, H.pt(cv0, .3, .3))
    print("load in flight:", c1._loader.isRunning())
t0 = time.time()
win.close(); app.processEvents()
print("closed in %.2fs" % (time.time() - t0), "win visible:", win.isVisible(), "dock visible:", dock.isVisible(),
      "modes:", [c.canvas().wl_mode() for c in quad.cells()], "loaders running:", [c._loader.isRunning() for c in quad.cells()])
del win
app.processEvents()
print("exit ok")
