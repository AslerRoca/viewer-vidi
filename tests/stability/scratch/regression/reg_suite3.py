"""Regression suite part 3: corrected re-runs (r04 tail, r06) + deeper r12 probe + ROI-TC cell switch."""
import os, sys, time, traceback
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
SCR = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/regression"
FRAMES = os.path.join(SCR, "frames2dt")
DCM1 = os.path.join(H.FIXTURES, "bpd1_20100101_2.dcm")
DCM2 = os.path.join(H.FIXTURES, "bpd1_20100102_1.dcm")
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
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
app, win = H.boot(); dock, quad, tree = win._dock, win._quad, win._tree
from viewer_vidi.data_model import SeriesType

def wait_2dt(cell, timeout=10):
    t0 = time.time()
    while time.time() - t0 < timeout and (cell._vol is None or cell._vol.ndim != 3): app.processEvents(); time.sleep(0.01)

def tree_proxy_index(path, timeout=15):
    parent = os.path.dirname(H.FIXTURES)
    tree._data_root = parent; tree._fs.setRootPath(parent); tree._set_root(parent)
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents(); time.sleep(0.02)
        d = tree._fs.index(H.FIXTURES)
        if d.isValid() and tree._proxy.mapFromSource(d).isValid():
            tree._tree.expand(tree._proxy.mapFromSource(d))
            f = tree._fs.index(path)
            if f.isValid() and tree._proxy.mapFromSource(f).isValid(): return tree._proxy.mapFromSource(f)
    return None

def reset_all():
    win._ws_btn.setChecked(False); app.processEvents()
    for c in quad.cells():
        for b in (c._roi_btn, c._tc_btn, c._roi_tc_btn):
            if b.isChecked(): b.setChecked(False)
    QTest.mouseClick(quad.cell_at(0).canvas(), Qt.LeftButton); app.processEvents()

@scenario
def r04b_tree_load_dock_hidden():
    cell = quad.active_cell(); canvas = cell.canvas()
    pf = tree_proxy_index(DCM2); check("r04b tree row found", pf is not None)
    tree._on_double_clicked(pf); app.processEvents()
    check("r04b tree load with dock hidden → drag mode", H.wait_loaded(app, cell) and cell.series_data().meta.series_dir == DCM2 and canvas.wl_mode() == "drag", canvas.wl_mode())
    check("r04b status bar", os.path.basename(DCM2) in win._status_series.text(), win._status_series.text())
    wc0, ww0 = canvas.wl()
    H.drag(app, canvas, H.pt(canvas, .3, .5), H.pt(canvas, .6, .3))
    check("r04b W/L drag after tree load", canvas.wl() != (wc0, ww0), f"{(wc0, ww0)}->{canvas.wl()}")
    check("r04b spins follow the drag", abs(win._wc_spin.value()-canvas.wl()[0]) < .6)
    # the tree's context-menu "Load" and double-click share series_selected; also check a second load replaces the first
    pf1 = tree_proxy_index(DCM1); tree._on_double_clicked(pf1); app.processEvents()
    check("r04b second tree load replaces series", H.wait_loaded(app, cell) and cell.series_data().meta.series_dir == DCM1)
    check("r04b invariants after reload", H.invariants(canvas) == [], str(H.invariants(canvas)))

@scenario
def r06b_space_play_and_ctrl_b():
    cell = quad.active_cell(); canvas = cell.canvas()
    assert H.load_file(app, cell, FRAMES); wait_2dt(cell)
    for dock_vis in (False, True):
        lab = "visible" if dock_vis else "hidden"
        win._ws_btn.setChecked(dock_vis); app.processEvents()
        canvas.setFocus(); app.processEvents()
        QTest.keyClick(canvas, Qt.Key_Space); app.processEvents()
        check(f"r06b Space starts playback (dock {lab})", cell._play_btn.isChecked() and cell._timer.isActive(), f"play={cell._play_btn.isChecked()} timer={cell._timer.isActive()}")
        t0 = cell._time_slider.value(); H.pump(app, 600)
        check(f"r06b playback advances time (dock {lab})", cell._time_slider.value() != t0, f"{t0}->{cell._time_slider.value()} interval={cell._timer.interval()}")
        QTest.keyClick(canvas, Qt.Key_Space); app.processEvents()
        check(f"r06b Space stops playback (dock {lab})", not cell._play_btn.isChecked() and not cell._timer.isActive())
        if dock_vis: check("r06b Space in paint mode painted nothing", canvas.mask_pixels() == 0)
    vis0 = tree.isVisible()
    QTest.keyClick(win, Qt.Key_B, Qt.ControlModifier); app.processEvents()
    check("r06b Ctrl+B toggles sidebar with dock visible", tree.isVisible() != vis0, f"{vis0}->{tree.isVisible()}")
    QTest.keyClick(win, Qt.Key_B, Qt.ControlModifier); app.processEvents()
    check("r06b Ctrl+B toggles back", tree.isVisible() == vis0)
    check("r06b dock still visible after sidebar toggle", dock.isVisible() and win._ws_btn.isChecked())
    # playback stop via load_meta (pre-existing): start play, load another series → timer stopped
    QTest.keyClick(canvas, Qt.Key_Space); app.processEvents()
    assert cell._timer.isActive()
    H.load_file(app, cell, DCM1)
    check("r06b load_meta stops playback", not cell._timer.isActive() and not cell._play_btn.isChecked())
    reset_all()

@scenario
def r12b_tc_panel_after_return():
    c0, c1 = quad.cell_at(0), quad.cell_at(1); panel = tree.tc_panel
    assert H.load_file(app, c0, FRAMES) and H.load_file(app, c1, DCM1); wait_2dt(c0)
    QTest.mouseClick(c0.canvas(), Qt.LeftButton); app.processEvents()
    c0._tc_btn.setChecked(True); app.processEvents()
    H.click(c0.canvas(), H.pt(c0.canvas(), .5, .5)); app.processEvents()
    l0 = len(panel._ax.lines); p0 = list(panel._points)
    check("r12b curve drawn", l0 == 1 and len(p0) == 1, f"lines={l0} pts={p0}")
    QTest.mouseClick(c1.canvas(), Qt.LeftButton); app.processEvents()
    QTest.mouseClick(c0.canvas(), Qt.LeftButton); app.processEvents()
    s1 = f"vis={panel.isVisible()} lines={len(panel._ax.lines)} pts={panel._points} canvas_pts={c0.canvas().tc_points()}"
    H.pump(app, 500); panel.grab(); app.processEvents()
    s2 = f"after pump+paint: lines={len(panel._ax.lines)} pts={panel._points}"
    check("r12b panel keeps the curve after returning to the TC cell", len(panel._ax.lines) == 1, s1 + " | " + s2)
    # does the next interaction bring it back?
    H.click(c0.canvas(), H.pt(c0.canvas(), .2, .7)); app.processEvents()
    check("r12b adding a point redraws both curves", len(panel._ax.lines) == 2 and len(c0.canvas().tc_points()) == 2, f"lines={len(panel._ax.lines)} pts={c0.canvas().tc_points()}")
    # same with ROI-TC: lasso, switch away and back
    c0._tc_btn.setChecked(False); c0._roi_tc_btn.setChecked(True); app.processEvents()
    cv = c0.canvas(); sq = [H.pt(cv, .5, .3), H.pt(cv, .75, .3), H.pt(cv, .75, .55), H.pt(cv, .5, .55), H.pt(cv, .5, .32)]
    H.press(cv, sq[0]); [H.move(cv, p, Qt.LeftButton) for p in sq[1:]]; H.release(cv, sq[-1]); app.processEvents()
    check("r12b ROI-TC curve drawn", len(cv._roi_tc_polys) == 1 and len(panel._ax.lines) == 1, f"polys={len(cv._roi_tc_polys)} lines={len(panel._ax.lines)}")
    QTest.mouseClick(c1.canvas(), Qt.LeftButton); app.processEvents(); QTest.mouseClick(cv, Qt.LeftButton); app.processEvents()
    check("r12b ROI-TC: panel after return", panel.isVisible() and len(panel._ax.lines) == 1, f"vis={panel.isVisible()} lines={len(panel._ax.lines)} polys={len(cv._roi_tc_polys)} mode={cv.wl_mode()}")
    c0._roi_tc_btn.setChecked(False); app.processEvents()
    reset_all()

@scenario
def r13_roi_tc_cell_switch_with_dock():
    c0, c1 = quad.cell_at(0), quad.cell_at(1); cv = c0.canvas()
    assert H.load_file(app, c0, FRAMES) and H.load_file(app, c1, DCM1); wait_2dt(c0)
    QTest.mouseClick(cv, Qt.LeftButton); app.processEvents()
    win._ws_btn.setChecked(True); app.processEvents()
    c0._roi_tc_btn.setChecked(True); app.processEvents()
    check("r13 ROI-TC mode with dock visible", cv.wl_mode() == "roi_tc")
    QTest.mouseClick(c1.canvas(), Qt.LeftButton); app.processEvents(); QTest.mouseClick(cv, Qt.LeftButton); app.processEvents()
    check("r13 cell 0 keeps roi_tc after cell switch (dock visible)", cv.wl_mode() == "roi_tc", f"mode={cv.wl_mode()} roi_tc_btn={c0._roi_tc_btn.isChecked()}")
    # and the cell-1 side: cell 1 (2-D) gets the dock tool, as designed
    check("r13 cell 1 got the dock tool", c1.canvas().wl_mode() == dock._current_tool(), c1.canvas().wl_mode())
    reset_all()

r04b_tree_load_dock_hidden(); r06b_space_play_and_ctrl_b(); r12b_tc_panel_after_return(); r13_roi_tc_cell_switch_with_dock()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} checks passed")
for n, ok, info in results:
    if not ok: print("FAILED:", n, info)
sys.exit(1 if n_fail else 0)
