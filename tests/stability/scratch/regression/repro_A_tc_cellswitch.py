"""Finding A: dock visible + TC mode on cell 0; activate cell 1, then cell 0 again.
Expected: cell 0 stays in tc mode (its TC button is still checked, panel visible).
Observed: canvas mode forced to the dock tool ("paint"); click stamps brush, no TC point.
Run: QT_QPA_PLATFORM=offscreen timeout 300 python repro_A_tc_cellswitch.py"""
import os, sys, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
FRAMES = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/regression/frames2dt"
DCM1 = os.path.join(H.FIXTURES, "bpd1_20100101_2.dcm")
app, win = H.boot(); quad, dock, tree = win._quad, win._dock, win._tree
c0, c1 = quad.cell_at(0), quad.cell_at(1); cv = c0.canvas()
assert H.load_file(app, c0, FRAMES) and H.load_file(app, c1, DCM1)
t0 = time.time()
while time.time() - t0 < 10 and (c0._vol is None or c0._vol.ndim != 3): app.processEvents(); time.sleep(.01)
QTest.mouseClick(cv, Qt.LeftButton); app.processEvents()
win._ws_btn.setChecked(True); app.processEvents()           # dock visible → paint
c0._tc_btn.setChecked(True); app.processEvents()             # cell TC button → tc mode
H.click(cv, H.pt(cv, .5, .5)); app.processEvents()
print("after TC click: mode", cv.wl_mode(), "tc_pts", cv.tc_points(), "panel", tree.tc_panel.isVisible())
QTest.mouseClick(c1.canvas(), Qt.LeftButton); app.processEvents()
QTest.mouseClick(cv, Qt.LeftButton); app.processEvents()
print("back on cell 0: mode", cv.wl_mode(), "| TC btn checked", c0._tc_btn.isChecked(), "| panel visible", tree.tc_panel.isVisible())
m0 = cv.mask_pixels(); n0 = len(cv.tc_points())
H.click(cv, H.pt(cv, .2, .7)); app.processEvents()
print("click → tc_pts", n0, "->", len(cv.tc_points()), "| mask px", m0, "->", cv.mask_pixels())
c0._tc_btn.setChecked(False); app.processEvents()
print("TC off: mode", cv.wl_mode(), "| dock tool", dock._current_tool(), "| Brush checked", dock._tool_btns["paint"].isChecked())
bad = cv.wl_mode() != "tc" or len(cv.tc_points()) != n0 + 1
sys.exit(1 if bad else 0)
