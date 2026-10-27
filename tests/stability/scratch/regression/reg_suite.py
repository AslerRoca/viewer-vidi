"""Regression suite: pre-existing viewer features after the annotation-workspace change.
Run:  QT_QPA_PLATFORM=offscreen timeout 300 python reg_suite.py 2> reg_suite.stderr
"""
import os, sys, time, traceback
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H

SCR = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/regression"
FRAMES = os.path.join(SCR, "frames2dt")
MR3D20 = os.path.join(SCR, "mr3d20")
MR500 = "/media/zsk/ressd/research/alldata_backup/mymri/Liver_3T_sub5_2026_07_05/DICOM/26070517/54450002"
NII3D = "/media/zsk/ressd/research/alldata_backup/Tongyu_Wang/radiology_qingyi/qingyi/+C/2035104/C.nii"
DCM0 = os.path.join(H.FIXTURES, "bpd1_20100101_1.dcm")
DCM1 = os.path.join(H.FIXTURES, "bpd1_20100101_2.dcm")

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
from PyQt5.QtGui import QWheelEvent, QKeyEvent
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
    return ev.isAccepted()

def rgb_snapshot(canvas):
    return None if canvas._rgb_buf is None else canvas._rgb_buf.copy()

# ───────────────────────────────────────────────────────────────────────────
@scenario
def s01_wl_drag_dock_hidden():
    cell = quad.active_cell(); canvas = cell.canvas()
    assert H.load_file(app, cell, DCM0)
    check("s01 default mode drag", canvas.wl_mode() == "drag", canvas.wl_mode())
    wc0, ww0 = canvas.wl()
    s_wc0, s_ww0 = win._wc_spin.value(), win._ww_spin.value()
    check("s01 toolbar spins match canvas after load", abs(s_wc0 - wc0) < 0.6 and abs(s_ww0 - ww0) < 0.6, f"spin {s_wc0},{s_ww0} canvas {wc0},{ww0}")
    H.drag(app, canvas, H.pt(canvas, 0.3, 0.5), H.pt(canvas, 0.6, 0.3))
    wc1, ww1 = canvas.wl()
    check("s01 W/L drag changes wl()", (wc1, ww1) != (wc0, ww0), f"{wc0},{ww0} -> {wc1},{ww1}")
    check("s01 drag right widens, up raises center", ww1 > ww0 and wc1 > wc0, f"{wc0},{ww0} -> {wc1},{ww1}")
    check("s01 toolbar spins follow drag", abs(win._wc_spin.value() - wc1) < 0.6 and abs(win._ww_spin.value() - ww1) < 0.6,
          f"spin {win._wc_spin.value()},{win._ww_spin.value()} canvas {wc1},{ww1}")

@scenario
def s02_wl_drag_after_dock_shown_hidden():
    cell = quad.active_cell(); canvas = cell.canvas()
    win._ws_btn.setChecked(True); app.processEvents()
    check("s02 dock visible -> paint mode", dock.isVisible() and canvas.wl_mode() == "paint", canvas.wl_mode())
    wc_a, ww_a = canvas.wl()
    H.drag(app, canvas, H.pt(canvas, 0.3, 0.5), H.pt(canvas, 0.6, 0.3))
    check("s02 drag in paint mode leaves W/L unchanged", canvas.wl() == (wc_a, ww_a), f"{(wc_a, ww_a)} -> {canvas.wl()}")
    check("s02 drag in paint mode painted mask", canvas.mask_pixels() > 0, canvas.mask_pixels())
    win._ws_btn.setChecked(False); app.processEvents()
    check("s02 dock hidden -> drag on all cells", not dock.isVisible() and all(c.canvas().wl_mode() == "drag" for c in quad.cells()))
    wc0, ww0 = canvas.wl()
    H.drag(app, canvas, H.pt(canvas, 0.3, 0.5), H.pt(canvas, 0.6, 0.3))
    wc1, ww1 = canvas.wl()
    check("s02 W/L drag works again after dock hidden", (wc1, ww1) != (wc0, ww0), f"{wc0},{ww0} -> {wc1},{ww1}")
    check("s02 spins follow", abs(win._wc_spin.value() - wc1) < 0.6 and abs(win._ww_spin.value() - ww1) < 0.6)
    check("s02 mask persists across dock hide (annotation kept)", canvas.mask_pixels() > 0, canvas.mask_pixels())
    # Reset W/L button restores header W/L
    sd = cell.series_data()
    win._quad.reset_wl(); app.processEvents()
    check("s02 Reset W/L restores header values", canvas.wl() == (sd.window_center, max(1.0, sd.window_width)), f"{canvas.wl()} vs {(sd.window_center, sd.window_width)}")
    # toolbar spin edit → canvas
    win._wc_spin.setValue(1234.0); app.processEvents()
    check("s02 toolbar spin drives canvas wc", canvas.wl()[0] == 1234.0, canvas.wl())

@scenario
def s03_roi_wl_button():
    cell = quad.active_cell(); canvas = cell.canvas()
    assert H.load_file(app, cell, DCM0)
    cell._roi_btn.setChecked(True); app.processEvents()
    check("s03 ROI button -> roi mode", canvas.wl_mode() == "roi", canvas.wl_mode())
    wc0, ww0 = canvas.wl()
    H.drag(app, canvas, H.pt(canvas, 0.4, 0.4), H.pt(canvas, 0.6, 0.6))
    wc1, ww1 = canvas.wl()
    px = canvas.displayed_pixels(); h, w = px.shape
    from viewer_vidi.windowing import wl_from_percentiles
    roi = px[int(0.4 * h):int(0.6 * h) + 1, int(0.4 * w):int(0.6 * w) + 1]
    ewc, eww = wl_from_percentiles(roi)
    check("s03 ROI drag sets W/L from region", (wc1, ww1) != (wc0, ww0), f"{wc0},{ww0} -> {wc1},{ww1}")
    check("s03 ROI W/L ≈ percentile stats of region", abs(wc1 - ewc) < 0.02 * max(1, abs(ewc)) + 50 and abs(ww1 - eww) < 0.05 * eww + 50, f"got {wc1},{ww1} expected ≈{ewc:.0f},{eww:.0f}")
    check("s03 spins follow ROI W/L", abs(win._wc_spin.value() - wc1) < 0.6 and abs(win._ww_spin.value() - ww1) < 0.6)
    check("s03 rubber band cleared", canvas._roi_start is None and canvas._roi_end is None)
    cell._roi_btn.setChecked(False); app.processEvents()
    check("s03 ROI off -> drag", canvas.wl_mode() == "drag", canvas.wl_mode())

@scenario
def s04_roi_wl_with_dock_visible():
    cell = quad.active_cell(); canvas = cell.canvas()
    win._ws_btn.setChecked(True); app.processEvents()
    cell._roi_btn.setChecked(True); app.processEvents()
    check("s04 ROI button overrides paint while dock shown", canvas.wl_mode() == "roi", canvas.wl_mode())
    wc0, ww0 = canvas.wl()
    H.drag(app, canvas, H.pt(canvas, 0.4, 0.4), H.pt(canvas, 0.6, 0.6))
    check("s04 ROI drag with dock shown sets W/L", canvas.wl() != (wc0, ww0), f"{(wc0, ww0)} -> {canvas.wl()}")
    cell._roi_btn.setChecked(False); app.processEvents()
    check("s04 ROI off with dock shown -> drag (dock tool btn still says Brush)", canvas.wl_mode() == "drag" and dock._tool_btns["paint"].isChecked(), canvas.wl_mode())
    win._ws_btn.setChecked(False); app.processEvents()

@scenario
def s05_tc_on_2dt():
    cell = quad.active_cell(); canvas = cell.canvas()
    assert H.load_file(app, cell, FRAMES)
    # wait for load_complete (all frames)
    t0 = time.time()
    while time.time() - t0 < 10 and (cell._vol is None or cell._vol.ndim != 3):
        app.processEvents(); time.sleep(0.01)
    sd = cell.series_data()
    check("s05 PNG dir loads as 2D-T with 6 timepoints", sd.series_type == SeriesType.S2DT and sd.n_timepoints == 6 and cell._vol.shape == (6, 96, 128), f"{sd.series_type} {cell._vol.shape}")
    check("s05 TC / ROI-TC buttons visible for 2D-T", cell._tc_btn.isVisible() and cell._roi_tc_btn.isVisible())
    check("s05 badge 2D-T", win._type_badge.text() == "2D-T", win._type_badge.text())
    panel = tree.tc_panel
    cell._tc_btn.setChecked(True); app.processEvents()
    check("s05 TC on -> tc mode + embedded panel visible", canvas.wl_mode() == "tc" and panel.isVisible(), f"{canvas.wl_mode()} vis={panel.isVisible()}")
    H.click(canvas, H.pt(canvas, 80 / 128, 40 / 96)); app.processEvents()
    pts = canvas.tc_points()
    check("s05 click adds TC point", len(pts) == 1, str(pts))
    check("s05 panel got the point and drew a curve", panel._points == pts and panel._ax is not None and len(panel._ax.lines) == 1, f"panel pts {panel._points} lines {len(panel._ax.lines) if panel._ax else None}")
    if panel._ax is not None and panel._ax.lines:
        ydata = np.asarray(panel._ax.lines[0].get_ydata())
        exp = cell._vol[:, pts[0][1], pts[0][0]]
        check("s05 curve equals voxel time course", ydata.shape == (6,) and np.allclose(ydata, exp), f"{ydata} vs {exp}")
        check("s05 curve is increasing (blob grows)", np.all(np.diff(ydata) > 0), str(ydata))
    H.click(canvas, H.pt(canvas, 0.2, 0.7)); app.processEvents()
    check("s05 second point", len(canvas.tc_points()) == 2 and len(panel._ax.lines) == 2)
    # right-click removes nearest
    H.click(canvas, H.pt(canvas, 0.2, 0.7), Qt.RightButton); app.processEvents()
    check("s05 right-click removes nearest point", len(canvas.tc_points()) == 1 and len(panel._ax.lines) == 1, str(canvas.tc_points()))
    # click on existing marker removes it
    H.click(canvas, H.pt(canvas, 80 / 128, 40 / 96)); app.processEvents()
    check("s05 click on marker removes it", len(canvas.tc_points()) == 0, str(canvas.tc_points()))
    # time slider via Shift+wheel
    t_before = cell._time_slider.value()
    acc = wheel(canvas, dy=-120, mods=Qt.ShiftModifier)
    check("s05 Shift+wheel steps time", cell._time_slider.value() == t_before + 1 and acc, f"{t_before} -> {cell._time_slider.value()}")
    check("s05 displayed pixels follow time", np.array_equal(canvas.displayed_pixels(), cell._vol[1]))
    cell._tc_btn.setChecked(False); app.processEvents()
    check("s05 TC off -> drag + panel hidden", canvas.wl_mode() == "drag" and not panel.isVisible())

def lasso(canvas, path):
    H.press(canvas, path[0])
    for p in path[1:]:
        H.move(canvas, p, Qt.LeftButton)
    H.release(canvas, path[-1])
    app.processEvents()

@scenario
def s06_roi_tc_on_2dt():
    cell = quad.active_cell(); canvas = cell.canvas()
    panel = tree.tc_panel
    cell._roi_tc_btn.setChecked(True); app.processEvents()
    check("s06 ROI-TC on -> roi_tc mode + panel visible", canvas.wl_mode() == "roi_tc" and panel.isVisible(), canvas.wl_mode())
    sq = [H.pt(canvas, 0.5, 0.3), H.pt(canvas, 0.75, 0.3), H.pt(canvas, 0.75, 0.55), H.pt(canvas, 0.5, 0.55), H.pt(canvas, 0.5, 0.32)]
    lasso(canvas, sq)
    check("s06 lasso adds polygon", len(canvas._roi_tc_polys) == 1, len(canvas._roi_tc_polys))
    check("s06 panel plots ROI curve", len(panel._roi_tc_polys) == 1 and len(panel._ax.lines) == 1, f"{len(panel._roi_tc_polys)} lines {len(panel._ax.lines)}")
    if panel._ax.lines:
        y = np.asarray(panel._ax.lines[0].get_ydata())
        check("s06 ROI mean increases with t", y.shape == (6,) and np.all(np.diff(y) > 0), str(y))
    sq2 = [H.pt(canvas, 0.1, 0.6), H.pt(canvas, 0.3, 0.6), H.pt(canvas, 0.3, 0.9), H.pt(canvas, 0.1, 0.9), H.pt(canvas, 0.1, 0.62)]
    lasso(canvas, sq2)
    check("s06 second polygon", len(canvas._roi_tc_polys) == 2 and len(panel._ax.lines) == 2)
    H.click(canvas, H.pt(canvas, 0.2, 0.75), Qt.RightButton); app.processEvents()
    check("s06 right-click inside removes that polygon", len(canvas._roi_tc_polys) == 1 and len(panel._ax.lines) == 1 and float(canvas._roi_tc_polys[0][0][0]) > 50, str([p[0] for p in canvas._roi_tc_polys]))
    cell._roi_tc_btn.setChecked(False); app.processEvents()
    check("s06 ROI-TC off clears polys and hides panel", canvas.wl_mode() == "drag" and canvas._roi_tc_polys == [] and not panel.isVisible())

@scenario
def s07_tc_with_dock_cell_switch():
    """Dock visible + TC on cell 0, switch to cell 1 and back: canvas mode vs TC button state."""
    cell = quad.cell_at(0); canvas = cell.canvas()
    other = quad.cell_at(1)
    assert H.load_file(app, other, DCM1)
    QTest.mouseClick(cell.canvas(), Qt.LeftButton); app.processEvents()
    win._ws_btn.setChecked(True); app.processEvents()
    cell._tc_btn.setChecked(True); app.processEvents()
    check("s07 TC on with dock shown -> tc mode", canvas.wl_mode() == "tc", canvas.wl_mode())
    QTest.mouseClick(other.canvas(), Qt.LeftButton); app.processEvents()
    check("s07 switched to cell 1", quad.active_cell() is other)
    QTest.mouseClick(cell.canvas(), Qt.LeftButton); app.processEvents()
    check("s07 back to cell 0", quad.active_cell() is cell)
    check("s07 cell 0 TC button still checked", cell._tc_btn.isChecked())
    check("s07 cell 0 canvas still in tc mode (TC button checked)", canvas.wl_mode() == "tc", f"mode={canvas.wl_mode()} tc_btn={cell._tc_btn.isChecked()}")
    cell._tc_btn.setChecked(False); app.processEvents()
    win._ws_btn.setChecked(False); app.processEvents()

@scenario
def s08_info_overlay():
    cell = quad.active_cell(); canvas = cell.canvas()
    assert H.load_file(app, cell, DCM0)
    check("s08 overlay off initially", canvas._overlay is None)
    cell._info_btn.setChecked(True); app.processEvents()
    check("s08 i button shows overlay", canvas._overlay is not None and len(canvas._ov_groups) > 0, f"groups={[g[0] for g in canvas._ov_groups]}")
    canvas.setFocus(); app.processEvents()
    QTest.keyClick(canvas, Qt.Key_I); app.processEvents()
    check("s08 I key toggles overlay off", canvas._overlay is None and not cell._info_btn.isChecked())
    QTest.keyClick(canvas, Qt.Key_I); app.processEvents()
    check("s08 I key toggles overlay on", canvas._overlay is not None and cell._info_btn.isChecked())
    canvas.grab(); app.processEvents()   # force paint → header hit rects
    rects = list(canvas._ov_header_rects)
    check("s08 header hit rects after paint", len(rects) == len(canvas._ov_groups) and len(rects) > 0, f"{len(rects)}")
    if rects:
        r, title = rects[0]
        wc0 = canvas.wl()
        H.click(canvas, r.center()); app.processEvents()
        check("s08 click header expands group", title in canvas._ov_expanded, f"{title} expanded={canvas._ov_expanded}")
        check("s08 header click does not start W/L drag", canvas.wl() == wc0 and canvas._drag_start is None)
        canvas.grab(); app.processEvents()
        n_rects_expanded = len(canvas._ov_header_rects)
        H.click(canvas, r.center()); app.processEvents()
        check("s08 click header again collapses", title not in canvas._ov_expanded)
    # overlay persists across slice/series? (expanded titles persist)
    cell._info_btn.setChecked(False); app.processEvents()
    check("s08 overlay off via button", canvas._overlay is None)

@scenario
def s09_invert_and_colormap():
    cell = quad.active_cell(); canvas = cell.canvas()
    assert H.load_file(app, cell, DCM0)
    before = rgb_snapshot(canvas)
    win._invert_btn.setChecked(True); app.processEvents()
    after = rgb_snapshot(canvas)
    check("s09 toolbar Invert inverts active cell", canvas.invert() and not np.array_equal(before, after))
    check("s09 inverted image ≈ 255 - original", np.allclose(after.astype(int), 255 - before.astype(int), atol=1))
    win._invert_btn.setChecked(False); app.processEvents()
    check("s09 invert off restores", np.array_equal(rgb_snapshot(canvas), before))
    # Ctrl+I shortcut
    win.activateWindow(); app.processEvents()
    QTest.keyClick(win, Qt.Key_I, Qt.ControlModifier); app.processEvents()
    ctrl_i = canvas.invert() and win._invert_btn.isChecked()
    check("s09 Ctrl+I shortcut toggles invert", ctrl_i, f"invert={canvas.invert()} btn={win._invert_btn.isChecked()}")
    if ctrl_i:
        QTest.keyClick(win, Qt.Key_I, Qt.ControlModifier); app.processEvents()
        check("s09 Ctrl+I again toggles off", not canvas.invert())
    else:
        win._invert_btn.setChecked(False); app.processEvents()
    # colormap
    base = rgb_snapshot(canvas)
    from viewer_vidi.colormaps import COLORMAP_NAMES
    other = next(n for n in COLORMAP_NAMES if n != "Gray")
    win._cmap_combo.setCurrentText(other); app.processEvents()
    cm = rgb_snapshot(canvas)
    check(f"s09 colormap combo '{other}' changes rendering on active cell", canvas._cmap_name == other and not np.array_equal(base, cm))
    check("s09 colormap applied to ALL cells", all(c.canvas()._cmap_name == other for c in quad.cells()))
    win._cmap_combo.setCurrentText("Gray"); app.processEvents()
    check("s09 back to Gray restores", np.array_equal(rgb_snapshot(canvas), base))

@scenario
def s10_dclick_fullscreen_modes():
    cell = quad.active_cell(); canvas = cell.canvas()
    assert H.load_file(app, cell, FRAMES)
    for mode_setup, label in ((lambda: None, "drag"),
                              (lambda: cell._roi_btn.setChecked(True), "roi"),
                              (lambda: cell._tc_btn.setChecked(True), "tc"),
                              (lambda: cell._roi_tc_btn.setChecked(True), "roi_tc")):
        mode_setup(); app.processEvents()
        check(f"s10 [{label}] mode set", canvas.wl_mode() == label, canvas.wl_mode())
        H.dclick(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents()
        check(f"s10 [{label}] dclick enters fullscreen", quad.is_fullscreen() and all((c is cell) == c.isVisible() for c in quad.cells()))
        H.dclick(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents()
        check(f"s10 [{label}] dclick exits fullscreen", not quad.is_fullscreen() and all(c.isVisible() for c in quad.cells()))
        wc = canvas.wl()
        check(f"s10 [{label}] dclick did not start W/L drag", canvas._drag_start is None)
        if label == "tc":
            check("s10 [tc] dclick did not add TC points (2 clicks → add then remove)", len(canvas.tc_points()) == 0, str(canvas.tc_points()))
        for b in (cell._roi_btn, cell._tc_btn, cell._roi_tc_btn):
            b.setChecked(False)
        app.processEvents()
    # with the dock visible in paint mode, dclick should still fullscreen (only poly is exempt)
    win._ws_btn.setChecked(True); app.processEvents()
    check("s10 paint mode", canvas.wl_mode() == "paint")
    H.dclick(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents()
    check("s10 [paint] dclick enters fullscreen", quad.is_fullscreen())
    H.dclick(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents()
    check("s10 [paint] dclick exits fullscreen", not quad.is_fullscreen())
    win._ws_btn.setChecked(False); app.processEvents()

@scenario
def s11_wheel_slice_time_zoom():
    cell = quad.active_cell(); canvas = cell.canvas()
    assert H.load_file(app, cell, NII3D, timeout=60)
    sd = cell.series_data()
    check("s11 NIfTI is 3D 56 slices", sd.series_type == SeriesType.S3D and sd.n_slices == 56, f"{sd.series_type} {sd.n_slices}")
    check("s11 badge 3D", win._type_badge.text() == "3D")
    z0 = cell._slice_slider.value()
    check("s11 slider starts mid", z0 == 28, z0)
    px0 = canvas.displayed_pixels().copy()
    wheel(canvas, dy=120)
    check("s11 wheel up -> slice -1", cell._slice_slider.value() == z0 - 1 and cell._cur_z == z0 - 1, f"{z0} -> {cell._slice_slider.value()}")
    check("s11 displayed slice changed", not np.array_equal(px0, canvas.displayed_pixels()))
    wheel(canvas, dy=-120); wheel(canvas, dy=-120)
    check("s11 wheel down twice -> slice +1", cell._slice_slider.value() == z0 + 1, cell._slice_slider.value())
    check("s11 displayed = vol[z]", np.array_equal(canvas.displayed_pixels(), cell._apply_flip(cell._vol[z0 + 1], acq=True)))
    # clamp at ends
    for _ in range(80): wheel(canvas, dy=-120)
    check("s11 slice clamps at max", cell._slice_slider.value() == 55, cell._slice_slider.value())
    # Ctrl+wheel zoom
    zz = canvas._zoom
    wheel(canvas, dy=120, mods=Qt.ControlModifier)
    check("s11 Ctrl+wheel zooms in", abs(canvas._zoom - zz * 1.15) < 1e-6 and cell._slice_slider.value() == 55, f"{zz} -> {canvas._zoom}")
    wheel(canvas, dy=-120, mods=Qt.ControlModifier)
    check("s11 Ctrl+wheel zooms out", abs(canvas._zoom - zz) < 1e-6, canvas._zoom)
    # Shift+wheel on 3D (no time axis) is a no-op without error
    wheel(canvas, dy=120, mods=Qt.ShiftModifier)
    check("s11 Shift+wheel on 3D no-op", cell._slice_slider.value() == 55 and cell._time_slider.value() == 0)
    # mask follows slice (same shape → kept) — invariants hold after slice change
    check("s11 invariants after slice scroll", H.invariants(canvas) == [], str(H.invariants(canvas)))
    # view change COR → MPR with different shape; invariants
    cell._cor_btn.click(); app.processEvents()
    check("s11 COR view renders", canvas.displayed_pixels() is not None and canvas.displayed_pixels().shape != px0.shape, str(canvas.displayed_pixels().shape))
    check("s11 invariants after MPR", H.invariants(canvas) == [], str(H.invariants(canvas)))
    cell._ax_btn.click(); app.processEvents()

@scenario
def s12_tree_double_click_load():
    cell = quad.active_cell()
    # tree root → fixtures dir, then double-click a DICOM file through the proxy
    tree._data_root = H.FIXTURES
    tree._fs.setRootPath(H.FIXTURES); tree._set_root(H.FIXTURES)
    tree.root_changed.emit(H.FIXTURES)
    check("s12 root_changed reaches dock.set_start_dir", dock._start_dir == H.FIXTURES, dock._start_dir)
    t0 = time.time(); src_idx = tree._fs.index(DCM1)
    while time.time() - t0 < 10 and not src_idx.isValid():
        app.processEvents(); time.sleep(0.02); src_idx = tree._fs.index(DCM1)
    check("s12 fs model indexes fixture file", src_idx.isValid())
    proxy_idx = tree._proxy.mapFromSource(src_idx)
    check("s12 proxy index valid", proxy_idx.isValid())
    win._ws_btn.setChecked(True); app.processEvents()      # dock present & visible
    tree._on_double_clicked(proxy_idx); app.processEvents()
    ok = H.wait_loaded(app, cell)
    sd = cell.series_data()
    check("s12 tree double-click loads into ACTIVE cell with dock visible", ok and sd is not None and sd.meta.series_dir == DCM1, str(sd.meta.series_dir if sd else None))
    check("s12 status bar shows series", DCM1.split("/")[-1] in win._status_series.text(), win._status_series.text())
    check("s12 after tree load with dock visible canvas is in dock tool mode", cell.canvas().wl_mode() == "drag" or cell.canvas().wl_mode() == "paint", cell.canvas().wl_mode())
    mode_after_tree_load = cell.canvas().wl_mode()
    win._ws_btn.setChecked(False); app.processEvents()
    tree._on_double_clicked(proxy_idx); app.processEvents()
    check("s12 tree double-click with dock hidden loads", H.wait_loaded(app, cell) and cell.canvas().wl_mode() == "drag")
    return mode_after_tree_load

@scenario
def s13_active_cell_sync():
    c0, c1 = quad.cell_at(0), quad.cell_at(1)
    assert H.load_file(app, c0, DCM0) and H.load_file(app, c1, FRAMES)
    QTest.mouseClick(c0.canvas(), Qt.LeftButton); app.processEvents()
    c0.set_wl(1000.0, 500.0); c1.set_wl(100.0, 50.0); c1.set_invert(True); app.processEvents()
    QTest.mouseClick(c1.canvas(), Qt.LeftButton); app.processEvents()
    check("s13 click activates cell 1", quad.active_cell() is c1)
    check("s13 spins sync to cell 1", win._wc_spin.value() == 100.0 and win._ww_spin.value() == 50.0, f"{win._wc_spin.value()},{win._ww_spin.value()}")
    check("s13 invert button syncs (checked)", win._invert_btn.isChecked())
    check("s13 badge syncs 2D-T", win._type_badge.text() == "2D-T", win._type_badge.text())
    QTest.mouseClick(c0.canvas(), Qt.LeftButton); app.processEvents()
    check("s13 back to cell 0: spins", win._wc_spin.value() == 1000.0 and win._ww_spin.value() == 500.0)
    check("s13 back to cell 0: invert unchecked, badge 2D", not win._invert_btn.isChecked() and win._type_badge.text() == "2D", win._type_badge.text())
    check("s13 cell 1 still inverted (per-cell)", c1.invert() and not c0.invert())
    # spin edit only affects active cell
    win._ww_spin.setValue(777.0); app.processEvents()
    check("s13 spin edit targets active cell only", c0.current_wl()[1] == 777.0 and c1.current_wl()[1] == 50.0)
    # invert toggle affects active only
    win._invert_btn.setChecked(True); app.processEvents()
    check("s13 invert btn affects active only", c0.invert() and c1.invert())
    win._invert_btn.setChecked(False); app.processEvents()
    c1.set_invert(False)
    # active-cell change while dock visible: tool applied to the new cell, old cell keeps its mode
    win._ws_btn.setChecked(True); app.processEvents()
    dock._tool_btns["poly"].setChecked(True); dock._apply_tool(); app.processEvents()
    QTest.mouseClick(c1.canvas(), Qt.LeftButton); app.processEvents()
    check("s13 dock tool follows active cell", c1.canvas().wl_mode() == "poly", c1.canvas().wl_mode())
    check("s13 previous cell keeps its mode", c0.canvas().wl_mode() == "poly")
    dock._tool_btns["paint"].setChecked(True); dock._apply_tool()
    win._ws_btn.setChecked(False); app.processEvents()
    check("s13 hide dock -> all drag", all(c.canvas().wl_mode() == "drag" for c in quad.cells()))
    QTest.mouseClick(c0.canvas(), Qt.LeftButton); app.processEvents()

@scenario
def s14_tilt_reader_no_permission():
    import io, contextlib
    from viewer_vidi import tilt_evdev
    from viewer_vidi.tilt_evdev import TiltWheelReader
    orig = tilt_evdev.find_tilt_devices
    tilt_evdev.find_tilt_devices = lambda: [os.path.join(SCR, "noperm_event")]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stderr(buf):
            r = TiltWheelReader(); ok = r.start()
    finally:
        tilt_evdev.find_tilt_devices = orig
    msg = buf.getvalue()
    check("s14 start() returns False without permission", ok is False, str(ok))
    check("s14 prints the usermod hint", "not readable" in msg and "usermod -aG input" in msg, msg.strip())
    check("s14 no fds left open", r._fds == {})
    tilt_evdev.find_tilt_devices = lambda: []
    try:
        with contextlib.redirect_stderr(buf):
            r2 = TiltWheelReader(); ok2 = r2.start()
    finally:
        tilt_evdev.find_tilt_devices = orig
    check("s14 no devices: False and silent", ok2 is False and buf.getvalue() == msg)
    # real reader in this process (user in input group): started → Qt tilt suppressed
    from viewer_vidi.view_cell import ViewCell
    check("s14 real reader state consistent", bool(win._tilt_reader._fds) == ViewCell.qt_tilt_suppressed, f"fds={len(win._tilt_reader._fds)} suppressed={ViewCell.qt_tilt_suppressed}")
    # tilt wheel event on a 2D-T cell: consumed, and steps only when Qt path is active
    cell = quad.cell_at(1)
    QTest.mouseClick(cell.canvas(), Qt.LeftButton); app.processEvents()
    t0 = cell._time_slider.value()
    acc = wheel(cell.canvas(), dy=0, dx=-120)
    stepped = cell._time_slider.value() != t0
    check("s14 tilt wheel: consumed; steps iff Qt path active", acc and stepped == (not ViewCell.qt_tilt_suppressed), f"acc={acc} stepped={stepped} suppressed={ViewCell.qt_tilt_suppressed}")
    QTest.mouseClick(quad.cell_at(0).canvas(), Qt.LeftButton); app.processEvents()

@scenario
def s15_close_cancels_loaders():
    c0, c1 = quad.cell_at(0), quad.cell_at(1)
    m = _make_series_meta(MR500)
    c0.load_meta(m); c1.load_meta(_make_series_meta(MR3D20))
    app.processEvents()
    check("s15 loaders running", c0._loader.isRunning())
    t0 = time.time()
    win.close(); app.processEvents()
    dt = time.time() - t0
    check("s15 close returns promptly", dt < 20, f"{dt:.2f}s")
    check("s15 all loaders stopped after close", all(not c._loader.isRunning() for c in quad.cells()), str([c._loader.isRunning() for c in quad.cells()]))
    check("s15 cancel flag set on all loaders", all(c._loader._cancel.is_set() for c in quad.cells()))
    H.pump(app, 300)
    check("s15 no late pixel delivery after close", c0._vol is None, str(None if c0._vol is None else c0._vol.shape))

s01_wl_drag_dock_hidden()
s02_wl_drag_after_dock_shown_hidden()
s03_roi_wl_button()
s04_roi_wl_with_dock_visible()
s05_tc_on_2dt()
s06_roi_tc_on_2dt()
s07_tc_with_dock_cell_switch()
s08_info_overlay()
s09_invert_and_colormap()
s10_dclick_fullscreen_modes()
s11_wheel_slice_time_zoom()
s12_tree_double_click_load()
s13_active_cell_sync()
s14_tilt_reader_no_permission()
s15_close_cancels_loaders()

n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} checks passed")
for n, ok, info in results:
    if not ok:
        print("FAILED:", n, info)
sys.exit(1 if n_fail else 0)
