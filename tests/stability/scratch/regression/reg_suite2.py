"""Regression suite part 2: fixed re-checks of part-1 artifacts + deeper scenarios.
Run:  QT_QPA_PLATFORM=offscreen timeout 300 python reg_suite2.py > reg_suite2.out 2> reg_suite2.stderr
"""
import os, sys, time, traceback
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H

SCR = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/regression"
FRAMES = os.path.join(SCR, "frames2dt")
NII3D = "/media/zsk/ressd/research/alldata_backup/Tongyu_Wang/radiology_qingyi/qingyi/+C/2035104/C.nii"
DCM0 = os.path.join(H.FIXTURES, "bpd1_20100101_1.dcm")
DCM1 = os.path.join(H.FIXTURES, "bpd1_20100101_2.dcm")
DCM2 = os.path.join(H.FIXTURES, "bpd1_20100101_3.dcm")

results = []
def check(name, cond, info=""):
    results.append((name, bool(cond), info))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""), flush=True)

def scenario(fn):
    def run(*a, **k):
        print(f"--- {fn.__name__}", flush=True)
        try:
            fn(*a, **k)
        except Exception:
            tb = traceback.format_exc()
            check(f"{fn.__name__} raised", False, tb.strip().splitlines()[-1])
            print(tb, file=sys.stderr, flush=True)
    return run

import numpy as np
from PyQt5.QtCore import Qt, QPoint, QPointF, QEvent
from PyQt5.QtGui import QWheelEvent
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest

app, win = H.boot()
dock, quad, tree = win._dock, win._quad, win._tree
from viewer_vidi.tree_panel import _make_series_meta
from viewer_vidi.data_model import SeriesType

def wheel(canvas, dy=120, dx=0, mods=Qt.NoModifier):
    r = canvas._dest_rect()
    pos = QPointF(r.center())
    ev = QWheelEvent(pos, canvas.mapToGlobal(r.center()), QPoint(0, 0), QPoint(dx, dy),
                     Qt.NoButton, mods, Qt.NoScrollPhase, False)
    QApplication.sendEvent(canvas, ev)
    app.processEvents()

def wait_2dt(cell, timeout=10):
    t0 = time.time()
    while time.time() - t0 < timeout and (cell._vol is None or cell._vol.ndim != 3):
        app.processEvents(); time.sleep(0.01)

def reset_all():
    """Dock hidden, every cell in drag mode, cell 0 active, cell buttons off."""
    win._ws_btn.setChecked(False); app.processEvents()
    for c in quad.cells():
        for b in (c._roi_btn, c._tc_btn, c._roi_tc_btn):
            if b.isChecked(): b.setChecked(False)
    QTest.mouseClick(quad.cell_at(0).canvas(), Qt.LeftButton); app.processEvents()
    if quad.is_fullscreen():
        H.dclick(quad.active_cell().canvas(), H.pt(quad.active_cell().canvas(), .5, .5)); app.processEvents()

# ───────────────────────────────────────────────────────────────────────────
@scenario
def r01_roi_wl_with_dock_visible():
    """Part-1 s04 dragged the same region twice -> same W/L (artifact). Change W/L first."""
    cell = quad.active_cell(); canvas = cell.canvas()
    assert H.load_file(app, cell, DCM0)
    win._ws_btn.setChecked(True); app.processEvents()
    cell._roi_btn.setChecked(True); app.processEvents()
    check("r01 ROI mode while dock shown", canvas.wl_mode() == "roi")
    cell.set_wl(100.0, 10.0); app.processEvents()
    H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.45, 0.45))
    wc1, ww1 = canvas.wl()
    px = canvas.displayed_pixels(); h, w = px.shape
    from viewer_vidi.windowing import wl_from_percentiles
    ewc, eww = wl_from_percentiles(px[int(.2*h):int(.45*h)+1, int(.2*w):int(.45*w)+1])
    check("r01 ROI drag with dock shown sets W/L from region", (wc1, ww1) != (100.0, 10.0) and abs(wc1-ewc) < 60 and abs(ww1-eww) < 0.05*eww+60, f"{wc1},{ww1} ≈ {ewc:.0f},{eww:.0f}")
    check("r01 spins follow", abs(win._wc_spin.value()-wc1) < .6 and abs(win._ww_spin.value()-ww1) < .6)
    check("r01 mask untouched by ROI drag", canvas.mask_pixels() == 0, canvas.mask_pixels())
    # cell ROI button off while dock visible: what mode does the canvas end in?
    cell._roi_btn.setChecked(False); app.processEvents()
    mode = canvas.wl_mode(); tool = dock._current_tool()
    check("r01 after ROI-off with dock visible: canvas mode == dock tool", mode == tool, f"canvas={mode} dock tool={tool} brush_btn_checked={dock._tool_btns['paint'].isChecked()}")
    wc0, ww0 = canvas.wl(); m0 = canvas.mask_pixels()
    H.drag(app, canvas, H.pt(canvas, 0.3, 0.5), H.pt(canvas, 0.6, 0.3))
    check("r01 drag after ROI-off (dock visible, Brush checked) paints instead of W/L", canvas.wl() == (wc0, ww0) and canvas.mask_pixels() > m0, f"wl {(wc0,ww0)}->{canvas.wl()} mask {m0}->{canvas.mask_pixels()}")
    reset_all()

@scenario
def r02_shift_wheel_time_exact_step():
    cell = quad.active_cell(); canvas = cell.canvas()
    assert H.load_file(app, cell, FRAMES); wait_2dt(cell)
    check("r02 2D-T loaded", cell.series_data().series_type == SeriesType.S2DT and cell._vol.shape[0] == 6)
    t0 = cell._time_slider.value(); z0 = cell._slice_slider.value()
    wheel(canvas, dy=-120, mods=Qt.ShiftModifier)
    check("r02 Shift+wheel down steps time by exactly +1", cell._time_slider.value() == t0 + 1, f"{t0}->{cell._time_slider.value()}")
    check("r02 slice slider untouched", cell._slice_slider.value() == z0)
    check("r02 pixels follow time", np.array_equal(canvas.displayed_pixels(), cell._vol[t0 + 1]))
    wheel(canvas, dy=120, mods=Qt.ShiftModifier)
    check("r02 Shift+wheel up steps back", cell._time_slider.value() == t0)
    # time clamps (no wrap) at ends for Shift+wheel
    for _ in range(10): wheel(canvas, dy=-120, mods=Qt.ShiftModifier)
    check("r02 Shift+wheel clamps at last frame", cell._time_slider.value() == 5, cell._time_slider.value())
    wheel(canvas, dy=-120, mods=Qt.ShiftModifier)
    check("r02 no wrap on Shift+wheel", cell._time_slider.value() == 5)
    # tilt wheel wraps (Qt path active since no evdev reader)
    from viewer_vidi.view_cell import ViewCell
    if not ViewCell.qt_tilt_suppressed:
        wheel(canvas, dy=0, dx=-120)
        check("r02 tilt wheel steps time by one, wrapping 5->0", cell._time_slider.value() == 0, cell._time_slider.value())
        wheel(canvas, dy=0, dx=120)
        check("r02 tilt back wraps 0->5", cell._time_slider.value() == 5, cell._time_slider.value())
    # plain wheel on 2D-T (no slices): time/slice unchanged, no error
    before = (cell._time_slider.value(), cell._slice_slider.value())
    wheel(canvas, dy=120)
    check("r02 plain wheel on 2D-T is a no-op", (cell._time_slider.value(), cell._slice_slider.value()) == before)
    # curve values are monotonic non-decreasing (fixture saturates at 255 → part-1 strict check was an artifact)
    y = cell._vol[:, 39, 79]
    check("r02 fixture time course non-decreasing", np.all(np.diff(y) >= 0), str(y))

@scenario
def r03_overlay_header_collapse():
    cell = quad.active_cell(); canvas = cell.canvas()
    assert H.load_file(app, cell, DCM0)
    cell._info_btn.setChecked(True); canvas.grab(); app.processEvents()
    def rect_for(title):
        canvas.grab(); app.processEvents()
        for r, t in canvas._ov_header_rects:
            if t == title: return r
        return None
    titles = [g[0] for g in canvas._ov_groups]
    check("r03 groups present", len(titles) >= 2, str(titles))
    t0 = titles[0]
    r_before = rect_for(t0)
    H.click(canvas, r_before.center()); app.processEvents()
    check("r03 click expands", t0 in canvas._ov_expanded)
    r_after = rect_for(t0)
    check("r03 header rect moves up after expansion (bottom-anchored column)", r_after is not None and r_after.top() < r_before.top(), f"{r_before.top()} -> {r_after.top() if r_after else None}")
    H.click(canvas, r_after.center()); app.processEvents()
    check("r03 click on the moved header collapses it", t0 not in canvas._ov_expanded, str(canvas._ov_expanded))
    # a second group: expand both, collapse both
    t1 = titles[1]
    H.click(canvas, rect_for(t0).center()); H.click(canvas, rect_for(t1).center()); app.processEvents()
    check("r03 two groups expanded", canvas._ov_expanded == {t0, t1}, str(canvas._ov_expanded))
    H.click(canvas, rect_for(t1).center()); H.click(canvas, rect_for(t0).center()); app.processEvents()
    check("r03 both collapsed", canvas._ov_expanded == set(), str(canvas._ov_expanded))
    # header click in paint mode (dock visible) must not paint
    win._ws_btn.setChecked(True); app.processEvents()
    m0 = canvas.mask_pixels()
    H.click(canvas, rect_for(t0).center()); app.processEvents()
    check("r03 header click in paint mode toggles group, paints nothing", t0 in canvas._ov_expanded and canvas.mask_pixels() == m0, f"mask {m0}->{canvas.mask_pixels()}")
    H.click(canvas, rect_for(t0).center()); app.processEvents()
    cell._info_btn.setChecked(False); app.processEvents()
    reset_all()

def tree_proxy_index(path, timeout=15):
    """Drive the real tree: root = parent of fixtures, expand fixtures dir, wait for the file row."""
    parent = os.path.dirname(H.FIXTURES)
    tree._data_root = parent
    tree._fs.setRootPath(parent); tree._set_root(parent)
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents(); time.sleep(0.02)
        d = tree._fs.index(H.FIXTURES)
        if d.isValid():
            pd = tree._proxy.mapFromSource(d)
            if pd.isValid():
                tree._tree.expand(pd)
                f = tree._fs.index(path)
                if f.isValid():
                    pf = tree._proxy.mapFromSource(f)
                    if pf.isValid():
                        return pf
    return None

@scenario
def r04_tree_double_click_with_dock():
    cell = quad.active_cell(); canvas = cell.canvas()
    win._ws_btn.setChecked(True); app.processEvents()
    pf = tree_proxy_index(DCM1)
    check("r04 tree shows the .dcm row once its dir is classified", pf is not None)
    if pf is None: return
    spins_before = (win._wc_spin.value(), win._ww_spin.value())
    tree._on_double_clicked(pf); app.processEvents()
    ok = H.wait_loaded(app, cell)
    sd = cell.series_data()
    check("r04 tree double-click loads into ACTIVE cell with dock visible", ok and sd is not None and sd.meta.series_dir == DCM1, str(sd.meta.series_dir if sd else None))
    check("r04 status bar shows the series", os.path.basename(DCM1) in win._status_series.text(), win._status_series.text())
    mode = canvas.wl_mode(); tool = dock._current_tool()
    check("r04 after tree load with dock visible: canvas mode == dock tool", mode == tool, f"canvas={mode} dock={tool}")
    wc0, ww0 = canvas.wl(); m0 = canvas.mask_pixels()
    H.drag(app, canvas, H.pt(canvas, 0.3, 0.5), H.pt(canvas, 0.6, 0.3))
    check("r04 drag after tree load (dock visible, Brush checked) paints, not W/L", canvas.wl() == (wc0, ww0) and canvas.mask_pixels() > m0, f"wl {(wc0,ww0)}->{canvas.wl()} mask {m0}->{canvas.mask_pixels()}")
    # pre-existing toolbar sync after a tree load (unchanged code path)
    check("r04 [preexisting path] toolbar spins reflect loaded series W/L", abs(win._wc_spin.value()-wc0) < .6 and abs(win._ww_spin.value()-ww0) < .6, f"spins {win._wc_spin.value()},{win._ww_spin.value()} canvas {wc0},{ww0} (before load {spins_before})")
    check("r04 [preexisting path] type badge set after tree load", win._type_badge.text() == "2D", repr(win._type_badge.text()))
    # dock hidden: tree load → drag mode, W/L drag works
    win._ws_btn.setChecked(False); app.processEvents()
    pf2 = tree_proxy_index(DCM2)
    tree._on_double_clicked(pf2); app.processEvents()
    check("r04 tree load with dock hidden", H.wait_loaded(app, cell) and cell.series_data().meta.series_dir == DCM2 and canvas.wl_mode() == "drag")
    wc0, ww0 = canvas.wl()
    H.drag(app, canvas, H.pt(canvas, 0.3, 0.5), H.pt(canvas, 0.6, 0.3))
    check("r04 W/L drag after tree load (dock hidden)", canvas.wl() != (wc0, ww0))
    reset_all()

@scenario
def r05_tc_cell_switch_with_dock():
    """Dock visible, TC on in cell 0, activate cell 1, back to cell 0."""
    c0, c1 = quad.cell_at(0), quad.cell_at(1); canvas = c0.canvas(); panel = tree.tc_panel
    assert H.load_file(app, c0, FRAMES) and H.load_file(app, c1, DCM1); wait_2dt(c0)
    QTest.mouseClick(canvas, Qt.LeftButton); app.processEvents()
    win._ws_btn.setChecked(True); app.processEvents()
    c0._tc_btn.setChecked(True); app.processEvents()
    H.click(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents()
    check("r05 TC point added with dock visible", len(canvas.tc_points()) == 1 and panel.isVisible())
    QTest.mouseClick(c1.canvas(), Qt.LeftButton); app.processEvents()
    QTest.mouseClick(canvas, Qt.LeftButton); app.processEvents()
    check("r05 back on cell 0", quad.active_cell() is c0)
    state = f"mode={canvas.wl_mode()} tc_btn={c0._tc_btn.isChecked()} panel_visible={panel.isVisible()} tc_pts={canvas.tc_points()}"
    check("r05 cell 0 keeps tc mode while its TC button is checked", canvas.wl_mode() == "tc", state)
    m0 = canvas.mask_pixels(); n0 = len(canvas.tc_points())
    H.click(canvas, H.pt(canvas, 0.2, 0.7)); app.processEvents()
    check("r05 click on cell 0 adds a TC point (not a brush stamp)", len(canvas.tc_points()) == n0 + 1 and canvas.mask_pixels() == m0, f"tc {n0}->{len(canvas.tc_points())} mask {m0}->{canvas.mask_pixels()}")
    c0._tc_btn.setChecked(False); app.processEvents()
    check("r05 TC off with dock visible -> canvas mode == dock tool", canvas.wl_mode() == dock._current_tool(), f"canvas={canvas.wl_mode()} dock={dock._current_tool()}")
    reset_all()

@scenario
def r06_space_play_and_ctrl_b():
    cell = quad.active_cell(); canvas = cell.canvas()
    assert H.load_file(app, cell, FRAMES); wait_2dt(cell)
    for dock_vis in (False, True):
        win._ws_btn.setChecked(dock_vis); app.processEvents()
        canvas.setFocus(); app.processEvents()
        QTest.keyClick(canvas, Qt.Key_Space); app.processEvents()
        check(f"r06 Space starts playback (dock {'visible' if dock_vis else 'hidden'})", cell._play_btn.isChecked() and cell._play_timer.isActive(), f"play={cell._play_btn.isChecked()}")
        t0 = cell._time_slider.value(); H.pump(app, 400)
        check(f"r06 playback advances time (dock {'visible' if dock_vis else 'hidden'})", cell._time_slider.value() != t0, f"{t0}->{cell._time_slider.value()}")
        QTest.keyClick(canvas, Qt.Key_Space); app.processEvents()
        check(f"r06 Space stops playback", not cell._play_btn.isChecked() and not cell._play_timer.isActive())
        if dock_vis:
            check("r06 Space in paint mode painted nothing", canvas.mask_pixels() == 0)
    vis0 = tree.isVisible()
    QTest.keyClick(win, Qt.Key_B, Qt.ControlModifier); app.processEvents()
    check("r06 Ctrl+B toggles sidebar with dock visible", tree.isVisible() != vis0, f"{vis0}->{tree.isVisible()}")
    QTest.keyClick(win, Qt.Key_B, Qt.ControlModifier); app.processEvents()
    check("r06 Ctrl+B toggles back", tree.isVisible() == vis0)
    check("r06 dock still visible after sidebar toggle", dock.isVisible() and win._ws_btn.isChecked())
    reset_all()

@scenario
def r07_right_drag_pan():
    cell = quad.active_cell(); canvas = cell.canvas()
    assert H.load_file(app, cell, DCM0)
    for mode_vis, label in ((False, "drag"), (True, "paint")):
        win._ws_btn.setChecked(mode_vis); app.processEvents()
        check(f"r07 [{label}] mode", canvas.wl_mode() == label, canvas.wl_mode())
        pan0 = (canvas._pan_x, canvas._pan_y); wl0 = canvas.wl(); m0 = canvas.mask_pixels()
        H.drag(app, canvas, H.pt(canvas, .4, .4), H.pt(canvas, .6, .55), button=Qt.RightButton)
        check(f"r07 [{label}] right-drag pans", (canvas._pan_x, canvas._pan_y) != pan0, f"{pan0}->{(canvas._pan_x, canvas._pan_y)}")
        check(f"r07 [{label}] right-drag leaves W/L and mask alone", canvas.wl() == wl0 and canvas.mask_pixels() == m0)
    reset_all()

@scenario
def r08_ctrl_i_with_dock_focus():
    cell = quad.active_cell(); canvas = cell.canvas()
    assert H.load_file(app, cell, DCM0)
    win._ws_btn.setChecked(True); app.processEvents()
    dock._brush_spin.setFocus(); app.processEvents()
    inv0 = canvas.invert()
    QTest.keyClick(dock._brush_spin, Qt.Key_I, Qt.ControlModifier); app.processEvents()
    check("r08 Ctrl+I with focus in the dock toggles invert", canvas.invert() != inv0 and win._invert_btn.isChecked() != inv0, f"{inv0}->{canvas.invert()}")
    QTest.keyClick(dock._brush_spin, Qt.Key_I, Qt.ControlModifier); app.processEvents()
    check("r08 Ctrl+I again restores", canvas.invert() == inv0)
    # Ctrl+Shift+W from a dock widget hides the dock; tools restored
    QTest.keyClick(dock._brush_spin, Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier); app.processEvents()
    check("r08 Ctrl+Shift+W hides dock and restores drag", not dock.isVisible() and canvas.wl_mode() == "drag" and not win._ws_btn.isChecked())
    reset_all()

@scenario
def r09_i_key_in_annotation_modes():
    cell = quad.active_cell(); canvas = cell.canvas()
    assert H.load_file(app, cell, DCM0)
    win._ws_btn.setChecked(True); app.processEvents()
    for tool in ("paint", "poly", "rect"):
        dock._tool_btns[tool].setChecked(True); dock._apply_tool(); app.processEvents()
        canvas.setFocus(); app.processEvents()
        QTest.keyClick(canvas, Qt.Key_I); app.processEvents()
        on = canvas._overlay is not None and cell._info_btn.isChecked()
        QTest.keyClick(canvas, Qt.Key_I); app.processEvents()
        check(f"r09 I key toggles overlay in {tool} mode", on and canvas._overlay is None, f"on={on} off={canvas._overlay is None}")
    # Enter in poly mode with no vertices: no crash, no overlay/play change
    dock._tool_btns["poly"].setChecked(True); dock._apply_tool(); app.processEvents()
    QTest.keyClick(canvas, Qt.Key_Return); QTest.keyClick(canvas, Qt.Key_Escape); app.processEvents()
    check("r09 Enter/Esc in empty poly: harmless", canvas.mask_pixels() == 0 and canvas._overlay is None)
    dock._tool_btns["paint"].setChecked(True); dock._apply_tool()
    reset_all()

@scenario
def r10_dclick_fullscreen_rect_poly():
    cell = quad.active_cell(); canvas = cell.canvas()
    assert H.load_file(app, cell, DCM0)
    win._ws_btn.setChecked(True); app.processEvents()
    dock._tool_btns["rect"].setChecked(True); dock._apply_tool(); app.processEvents()
    H.dclick(canvas, H.pt(canvas, .5, .5)); app.processEvents()
    check("r10 [rect] dclick enters fullscreen", quad.is_fullscreen())
    H.dclick(canvas, H.pt(canvas, .5, .5)); app.processEvents()
    check("r10 [rect] dclick exits fullscreen", not quad.is_fullscreen())
    check("r10 [rect] dclick left no crop rect", canvas.crop_rect() is None, str(canvas.crop_rect()))
    dock._tool_btns["poly"].setChecked(True); dock._apply_tool(); app.processEvents()
    H.dclick(canvas, H.pt(canvas, .5, .5)); app.processEvents()
    check("r10 [poly] dclick does not fullscreen (documented)", not quad.is_fullscreen())
    dock._tool_btns["paint"].setChecked(True); dock._apply_tool()
    reset_all()

@scenario
def r11_wheel_zoom_3d_after_dock_cycle():
    """Wheel handling on 3-D after the dock was shown and hidden (eventFilter still installed)."""
    cell = quad.active_cell(); canvas = cell.canvas()
    assert H.load_file(app, cell, NII3D, timeout=60)
    win._ws_btn.setChecked(True); app.processEvents()
    z0 = cell._slice_slider.value()
    wheel(canvas, dy=-120)
    check("r11 wheel scrolls slice with dock visible (paint mode)", cell._slice_slider.value() == z0 + 1, f"{z0}->{cell._slice_slider.value()}")
    check("r11 invariants after slice scroll in paint mode", H.invariants(canvas) == [], str(H.invariants(canvas)))
    win._ws_btn.setChecked(False); app.processEvents()
    zz = canvas._zoom
    wheel(canvas, dy=120, mods=Qt.ControlModifier)
    check("r11 Ctrl+wheel zoom after dock hidden", abs(canvas._zoom - zz*1.15) < 1e-6 and cell._slice_slider.value() == z0 + 1)
    wheel(canvas, dy=-120, mods=Qt.ControlModifier)
    wheel(canvas, dy=120)
    check("r11 wheel slice after dock hidden", cell._slice_slider.value() == z0)
    reset_all()

@scenario
def r12_active_cell_change_refreshes_tc_panel():
    c0, c1 = quad.cell_at(0), quad.cell_at(1); panel = tree.tc_panel
    assert H.load_file(app, c0, FRAMES) and H.load_file(app, c1, DCM1); wait_2dt(c0)
    QTest.mouseClick(c0.canvas(), Qt.LeftButton); app.processEvents()
    c0._tc_btn.setChecked(True); app.processEvents()
    H.click(c0.canvas(), H.pt(c0.canvas(), .5, .5)); app.processEvents()
    check("r12 panel shows cell 0 curve", panel.isVisible() and len(panel._ax.lines) == 1)
    QTest.mouseClick(c1.canvas(), Qt.LeftButton); app.processEvents()
    check("r12 activating a 2-D cell hides/clears the panel", not panel.isVisible() or len(panel._ax.lines) == 0, f"vis={panel.isVisible()} lines={len(panel._ax.lines) if panel._ax else None}")
    QTest.mouseClick(c0.canvas(), Qt.LeftButton); app.processEvents()
    check("r12 back to cell 0 restores panel with its curve", panel.isVisible() and len(panel._ax.lines) == 1, f"vis={panel.isVisible()} lines={len(panel._ax.lines) if panel._ax else None}")
    c0._tc_btn.setChecked(False); app.processEvents()
    reset_all()

r01_roi_wl_with_dock_visible()
r02_shift_wheel_time_exact_step()
r03_overlay_header_collapse()
r04_tree_double_click_with_dock()
r05_tc_cell_switch_with_dock()
r06_space_play_and_ctrl_b()
r07_right_drag_pan()
r08_ctrl_i_with_dock_focus()
r09_i_key_in_annotation_modes()
r10_dclick_fullscreen_rect_poly()
r11_wheel_zoom_3d_after_dock_cycle()
r12_active_cell_change_refreshes_tc_panel()

n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} checks passed")
for n, ok, info in results:
    if not ok:
        print("FAILED:", n, info)
sys.exit(1 if n_fail else 0)
