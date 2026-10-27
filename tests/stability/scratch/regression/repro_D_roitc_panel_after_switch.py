"""Finding D (pre-existing): ROI-TC on a 2D-T cell; activate another panel, then come back.
Expected: embedded TC panel visible again with the ROI curve; new lassos update it.
Observed: panel stays hidden (ViewCell.is_tc_active() checks only the TC button) and
later lassos neither re-show nor update it (curve count stays stale).
Run: QT_QPA_PLATFORM=offscreen timeout 300 python repro_D_roitc_panel_after_switch.py"""
import os, sys, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
from PyQt5.QtCore import Qt
FRAMES = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/regression/frames2dt"
DCM1 = os.path.join(H.FIXTURES, "bpd1_20100101_2.dcm")
app, win = H.boot(); quad, tree = win._quad, win._tree; panel = tree.tc_panel
c0, c1 = quad.cell_at(0), quad.cell_at(1); cv = c0.canvas()
assert H.load_file(app, c0, FRAMES) and H.load_file(app, c1, DCM1)
t0 = time.time()
while time.time() - t0 < 10 and (c0._vol is None or c0._vol.ndim != 3): app.processEvents(); time.sleep(.01)
def activate(cell):
    c = cell.canvas(); p = H.pt(c, .03, .03); H.press(c, p); H.release(c, p); app.processEvents()
def lasso(pts):
    H.press(cv, pts[0]); [H.move(cv, p, Qt.LeftButton) for p in pts[1:]]; H.release(cv, pts[-1]); app.processEvents()
activate(c0)
c0._roi_tc_btn.setChecked(True); app.processEvents()
lasso([H.pt(cv, .5, .3), H.pt(cv, .75, .3), H.pt(cv, .75, .55), H.pt(cv, .5, .55), H.pt(cv, .5, .32)])
print("after lasso: panel visible", panel.isVisible(), "| polys", len(cv._roi_tc_polys), "| curves", len(panel._ax.lines))
activate(c1)
print("cell 1 active: panel visible", panel.isVisible())
activate(c0)
print("back on cell 0: mode", cv.wl_mode(), "| ROI-TC btn", c0._roi_tc_btn.isChecked(), "| panel visible", panel.isVisible(), "| curves", len(panel._ax.lines))
lasso([H.pt(cv, .1, .6), H.pt(cv, .3, .6), H.pt(cv, .3, .9), H.pt(cv, .1, .9), H.pt(cv, .1, .62)])
print("second lasso: polys", len(cv._roi_tc_polys), "| panel visible", panel.isVisible(), "| curves", len(panel._ax.lines))
sys.exit(0 if panel.isVisible() and len(panel._ax.lines) == 2 else 1)
