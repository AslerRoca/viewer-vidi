"""Regression suite part 4: corrected playback probe (sampled) and TC-panel-on-return probes
with the activation click placed away from TC markers."""
import os, sys, time, traceback
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
SCR = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/regression"
FRAMES = os.path.join(SCR, "frames2dt"); DCM1 = os.path.join(H.FIXTURES, "bpd1_20100101_2.dcm")
results = []
def check(name, cond, info=""):
    results.append((name, bool(cond), info)); print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""), flush=True)
def scenario(fn):
    def run():
        print(f"--- {fn.__name__}", flush=True)
        try: fn()
        except Exception:
            tb = traceback.format_exc(); check(f"{fn.__name__} raised", False, tb.strip().splitlines()[-1]); print(tb, file=sys.stderr, flush=True)
    return run
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
app, win = H.boot(); dock, quad, tree = win._dock, win._quad, win._tree
def wait_2dt(cell, timeout=10):
    t0 = time.time()
    while time.time() - t0 < timeout and (cell._vol is None or cell._vol.ndim != 3): app.processEvents(); time.sleep(0.01)
def activate(cell):
    """Activate a cell with a click in its top-left image corner (no TC marker there)."""
    cv = cell.canvas(); p = H.pt(cv, .03, .03); H.press(cv, p); H.release(cv, p); app.processEvents()
def pump_sample(cell, ms):
    seen = set(); t0 = time.time()
    while (time.time() - t0) * 1000 < ms:
        app.processEvents(); seen.add(cell._time_slider.value()); time.sleep(.005)
    return seen

@scenario
def p01_playback_sampled():
    cell = quad.active_cell(); canvas = cell.canvas()
    assert H.load_file(app, cell, FRAMES); wait_2dt(cell)
    for dock_vis in (False, True):
        lab = "visible" if dock_vis else "hidden"
        win._ws_btn.setChecked(dock_vis); app.processEvents(); canvas.setFocus(); app.processEvents()
        QTest.keyClick(canvas, Qt.Key_Space); app.processEvents()
        seen = pump_sample(cell, 450)
        QTest.keyClick(canvas, Qt.Key_Space); app.processEvents()
        check(f"p01 Space playback cycles frames (dock {lab})", len(seen) >= 3 and not cell._timer.isActive(), f"frames seen {sorted(seen)}")
    win._ws_btn.setChecked(False); app.processEvents()

@scenario
def p02_tc_panel_on_return():
    c0, c1 = quad.cell_at(0), quad.cell_at(1); cv = c0.canvas(); panel = tree.tc_panel
    assert H.load_file(app, c0, FRAMES) and H.load_file(app, c1, DCM1); wait_2dt(c0)
    activate(c0)
    c0._tc_btn.setChecked(True); app.processEvents()
    H.click(cv, H.pt(cv, .5, .5)); app.processEvents()
    check("p02 TC curve drawn", len(cv.tc_points()) == 1 and len(panel._ax.lines) == 1)
    activate(c1)
    check("p02 2-D cell active: panel hidden, cell 0 points kept", not panel.isVisible() and len(cv.tc_points()) == 1, f"vis={panel.isVisible()} pts={cv.tc_points()}")
    activate(c0)
    check("p02 back on TC cell: panel visible with its curve, points kept", panel.isVisible() and len(panel._ax.lines) == 1 and len(cv.tc_points()) == 1 and cv.wl_mode() == "tc", f"vis={panel.isVisible()} lines={len(panel._ax.lines)} pts={cv.tc_points()} mode={cv.wl_mode()}")
    c0._tc_btn.setChecked(False); app.processEvents()
    check("p02 TC off hides panel", not panel.isVisible())
    # ROI-TC: lasso, switch away and back — is the panel restored?
    c0._roi_tc_btn.setChecked(True); app.processEvents()
    sq = [H.pt(cv, .5, .3), H.pt(cv, .75, .3), H.pt(cv, .75, .55), H.pt(cv, .5, .55), H.pt(cv, .5, .32)]
    H.press(cv, sq[0]); [H.move(cv, p, Qt.LeftButton) for p in sq[1:]]; H.release(cv, sq[-1]); app.processEvents()
    n_lines = len(panel._ax.lines)
    check("p02 ROI-TC panel visible with ROI curve", panel.isVisible() and len(cv._roi_tc_polys) == 1 and n_lines >= 1, f"vis={panel.isVisible()} lines={n_lines}")
    activate(c1); activate(c0)
    check("p02 [preexisting?] back on ROI-TC cell: panel visible again", panel.isVisible(), f"vis={panel.isVisible()} mode={cv.wl_mode()} roi_tc_btn={c0._roi_tc_btn.isChecked()} polys={len(cv._roi_tc_polys)} lines={len(panel._ax.lines)}")
    # does a new lasso bring the panel back?
    sq2 = [H.pt(cv, .1, .6), H.pt(cv, .3, .6), H.pt(cv, .3, .9), H.pt(cv, .1, .9), H.pt(cv, .1, .62)]
    H.press(cv, sq2[0]); [H.move(cv, p, Qt.LeftButton) for p in sq2[1:]]; H.release(cv, sq2[-1]); app.processEvents()
    check("p02 new lasso after return: polys=2, panel visible", len(cv._roi_tc_polys) == 2 and panel.isVisible(), f"polys={len(cv._roi_tc_polys)} vis={panel.isVisible()} lines={len(panel._ax.lines)}")
    c0._roi_tc_btn.setChecked(False); app.processEvents()

p01_playback_sampled(); p02_tc_panel_on_return()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} checks passed")
for n, ok, info in results:
    if not ok: print("FAILED:", n, info)
sys.exit(1 if n_fail else 0)
