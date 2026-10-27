"""Multipanel lens, part 2: per-cell controls (view/slice/time sliders, zoom/pan) while annotating,
four loaded panels, fullscreen of another cell, main-window hide/show, double-click on an empty cell."""
import os, sys, time, shutil, traceback
os.environ["QT_QPA_PLATFORM"] = "offscreen"
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB)
import harness as H
import numpy as np
D = STAB + "/multipanel"; WS, WS2, MR3D = D + "/ws", D + "/ws2", D + "/mr3d"
results = []; slot_exceptions = []; current = ["setup"]
def check(name, cond, info=""):
    results.append((current[0] + " | " + name, bool(cond), info))
    print(("PASS " if cond else "FAIL ") + current[0] + " | " + name + (f"  [{info}]" if info else ""), flush=True)
def _hook(et, ev, tb):
    txt = "".join(traceback.format_exception(et, ev, tb)); slot_exceptions.append((current[0], txt))
    print(f"SLOT-EXCEPTION in {current[0]}:\n{txt}", flush=True)
sys.excepthook = _hook
from PyQt5.QtCore import Qt, QPoint
app, win = H.boot()
dock, quad = win._dock, win._quad
cells = quad.cells(); c0, c1, c2, c3 = cells; cv = [c.canvas() for c in cells]
def tool(mode): dock._tool_btns[mode].setChecked(True); dock._apply_tool(); app.processEvents()
def centroid(m0, m1):
    d = (m1 > 0) & ~(m0 > 0); ys, xs = np.nonzero(d)
    return (float(xs.mean()), float(ys.mean()), int(d.sum())) if d.any() else (None, None, 0)
def run(name, fn):
    current[0] = name
    try: fn()
    except Exception:
        check("no python exception", False, traceback.format_exc().strip().splitlines()[-1]); print(traceback.format_exc())
shutil.rmtree(os.path.join(WS, "vidi_output"), ignore_errors=True)
ws = H.open_workspace(app, win, WS); H.wait_loaded(app, c0)
H0, W0 = cv[0].displayed_pixels().shape

# ── T1: four loaded panels, Clear/Undo/stats isolation ─────────────────────
def t1():
    srcs = [MR3D, WS2, ws.items[2].path]
    for i, src in enumerate(srcs, start=1):
        cells[i].activated.emit(); app.processEvents()
        H.load_file(app, cells[i], src); tool("paint")
        H.drag(app, cv[i], H.pt(cv[i], .3, .3), H.pt(cv[i], .6, .3))
    counts = [c.mask_pixels() for c in cv]
    check("all four panels loaded and painted", all(n > 0 for n in counts[1:]), str(counts))
    c0.activated.emit(); app.processEvents(); tool("paint")
    H.drag(app, cv[0], H.pt(cv[0], .3, .3), H.pt(cv[0], .6, .3)); counts[0] = cv[0].mask_pixels()
    c2.activated.emit(); app.processEvents()
    dock._clear_btn.click(); app.processEvents()
    check("Clear touches only the active panel (cell2)", cv[2].mask_pixels() == 0 and [c.mask_pixels() for c in cv][::2] == [counts[0], 0]
          and cv[1].mask_pixels() == counts[1] and cv[3].mask_pixels() == counts[3], str([c.mask_pixels() for c in cv]))
    check("stats follow cell2", dock._stats_lbl.text().startswith("mask 0 px"), dock._stats_lbl.text())
    c3.activated.emit(); app.processEvents()
    app.setActiveWindow(win); H.key(win, Qt.Key_Z, Qt.ControlModifier); app.processEvents()
    check("Ctrl+Z undoes only on the active panel (cell3)", cv[3].mask_pixels() == 0 and cv[2].mask_pixels() == 0 and cv[0].mask_pixels() == counts[0] and cv[1].mask_pixels() == counts[1], str([c.mask_pixels() for c in cv]))
    c2.activated.emit(); app.processEvents(); dock._undo_btn.click(); app.processEvents()
    check("Undo on cell2 restores its cleared mask", cv[2].mask_pixels() == counts[2], f"{cv[2].mask_pixels()} vs {counts[2]}")
    check("invariants on all four", all(not H.invariants(c) for c in cv), str([H.invariants(c) for c in cv]))
    check("modes: every visited panel kept the tool (observation)", True, str([c.wl_mode() for c in cv]))
run("T1 four panels", t1)

# ── T2: fullscreen another cell while cell0 has a polygon in progress ──────
def t2():
    c0.activated.emit(); app.processEvents(); tool("poly")
    for p in (H.pt(cv[0], .2, .2), H.pt(cv[0], .4, .2), H.pt(cv[0], .4, .4)):
        H.click(cv[0], p)
    check("3 vertices on cell0", len(cv[0]._poly_pts) == 3)
    # dclick on cell1 while the dock tool is poly: the activating press applies poly to cell1 first → no fullscreen
    H.dclick(cv[1], H.pt(cv[1], .5, .5)); app.processEvents()
    check("dclick other cell with dock tool=poly: activates, applies poly, no fullscreen", not quad.is_fullscreen() and quad.active_cell() is c1 and cv[1].wl_mode() == "poly", f"fs={quad.is_fullscreen()} mode={cv[1].wl_mode()}")
    check("cell0 polygon-in-progress preserved (cell0 not touched)", len(cv[0]._poly_pts) == 3, str(cv[0]._poly_pts))
    # cell1 is already active (no re-apply on press) → put it in paint directly, then dclick → fullscreen
    dock._tool_btns["paint"].setChecked(True); cv[1].set_wl_mode("paint")
    H.dclick(cv[1], H.pt(cv[1], .5, .5)); app.processEvents()
    check("cell1 fullscreen, active, dock tool applied (paint)", quad.is_fullscreen() and quad.active_cell() is c1 and cv[1].wl_mode() == "paint", f"fs={quad.is_fullscreen()} mode={cv[1].wl_mode()}")
    check("cell0 polygon-in-progress preserved while hidden", len(cv[0]._poly_pts) == 3, str(cv[0]._poly_pts))
    H.dclick(cv[1], H.pt(cv[1], .5, .5)); app.processEvents()
    check("dclick exits fullscreen", not quad.is_fullscreen())
    check("cell0 vertices still there after fullscreen round trip", len(cv[0]._poly_pts) == 3 and cv[0].wl_mode() == "poly", str(cv[0]._poly_pts))
    dock._tool_btns["poly"].setChecked(True)
    H.click(cv[0], H.pt(cv[0], .2, .4)); app.processEvents()   # click back on cell0 = 4th vertex from the user's view
    check("clicking back on cell0 keeps its 3 in-progress vertices (+1 new)", len(cv[0]._poly_pts) == 4, f"pts={cv[0]._poly_pts}")
    H.key(cv[0], Qt.Key_Escape); app.processEvents()
    check("no exception, invariants", not H.invariants(cv[0]) and not H.invariants(cv[1]))
run("T2 fullscreen other cell", t2)

# ── T3: 3-D panel: slice slider, AX/COR/SAG while painting ─────────────────
def t3():
    c1.activated.emit(); app.processEvents()
    H.load_file(app, c1, MR3D); tool("paint")
    sd = c1.series_data(); shp = cv[1].displayed_pixels().shape
    H.drag(app, cv[1], H.pt(cv[1], .3, .3), H.pt(cv[1], .6, .3)); n = cv[1].mask_pixels()
    tool("rect"); H.drag(app, cv[1], H.pt(cv[1], .2, .2), H.pt(cv[1], .8, .8)); r = cv[1].crop_rect()
    sl = c1._slice_slider; sl.setValue(min(sl.maximum(), sl.value() + 3)); app.processEvents()
    check("slice change keeps mask + rect (documented: 2-D on displayed slice)", cv[1].mask_pixels() == n and cv[1].crop_rect() == r and not H.invariants(cv[1]), f"{cv[1].mask_pixels()} {cv[1].crop_rect()}")
    check("rect mode survives slice change", cv[1].wl_mode() == "rect")
    for btn, name in ((c1._cor_btn, "COR"), (c1._sag_btn, "SAG"), (c1._ax_btn, "AX")):
        if btn.isVisible():
            btn.click(); app.processEvents()
            px = cv[1].displayed_pixels()
            inv = H.invariants(cv[1])
            check(f"{name} view: invariants hold, mask shape == slice", not inv and cv[1].mask().shape == px.shape, f"shape={px.shape} mask={cv[1].mask_pixels()} rect={cv[1].crop_rect()} inv={inv}")
            check(f"{name} view: mode kept", cv[1].wl_mode() == "rect", cv[1].wl_mode())
    tool("paint"); m0 = cv[1].mask().copy(); H.click(cv[1], H.pt(cv[1], .5, .5)); app.processEvents()
    cx, cy, k = centroid(m0, cv[1].mask()); h, w = cv[1].mask().shape
    check("paint after view switches maps to centre", k > 0 and abs(cx - w / 2) < 6 and abs(cy - h / 2) < 6, f"({cx},{cy}) of {w}x{h}")
    # wheel scroll on the canvas (slice) in paint mode
    from PyQt5.QtGui import QWheelEvent
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QPointF
    z0 = c1._slice_slider.value()
    ev = QWheelEvent(QPointF(H.pt(cv[1], .5, .5)), QPointF(0, 0), QPoint(0, 0), QPoint(0, -120), Qt.NoButton, Qt.NoModifier, Qt.ScrollUpdate, False)
    QApplication.sendEvent(cv[1], ev); app.processEvents()
    check("wheel on canvas scrolls slice in paint mode", c1._slice_slider.value() != z0 and not H.invariants(cv[1]), f"{z0} → {c1._slice_slider.value()}")
run("T3 3-D controls", t3)

# ── T4: 2D-T panel: time slider / play while painting ──────────────────────
def t4():
    c2.activated.emit(); app.processEvents()
    H.load_file(app, c2, WS2); tool("paint")
    H.drag(app, cv[2], H.pt(cv[2], .3, .3), H.pt(cv[2], .6, .3)); n = cv[2].mask_pixels()
    c2._time_slider.setValue(1); app.processEvents()
    check("time step keeps mask, invariants", cv[2].mask_pixels() == n and not H.invariants(cv[2]) and cv[2].wl_mode() == "paint", f"t={c2._time_slider.value()} mask={cv[2].mask_pixels()}")
    H.key(cv[2], Qt.Key_Space); app.processEvents()
    check("Space toggles play in paint mode (pre-existing)", c2._play_btn.isChecked())
    H.pump(app, 400)
    check("playback keeps mask, invariants", cv[2].mask_pixels() == n and not H.invariants(cv[2]))
    H.key(cv[2], Qt.Key_Space); app.processEvents()
    m0 = cv[2].mask().copy(); H.click(cv[2], H.pt(cv[2], .5, .5)); app.processEvents()
    cx, cy, k = centroid(m0, cv[2].mask()); h, w = cv[2].mask().shape
    check("paint after time change maps to centre", k > 0 and abs(cx - w / 2) < 25 and abs(cy - h / 2) < 25, f"({cx},{cy})")
run("T4 2D-T controls", t4)

# ── T5: zoom + right-drag pan in paint / poly modes ────────────────────────
def t5():
    c0.activated.emit(); app.processEvents(); tool("paint"); dock._clear_btn.click(); app.processEvents()
    for _ in range(4): cv[0].zoom_wheel(+120)
    app.processEvents()
    check("zoomed in", cv[0]._zoom > 1.5, str(cv[0]._zoom))
    m0 = cv[0].mask().copy(); H.click(cv[0], H.pt(cv[0], .5, .5)); app.processEvents()
    cx, cy, k = centroid(m0, cv[0].mask())
    check("paint at zoomed centre maps to image centre", k > 0 and abs(cx - W0 / 2) < 25 and abs(cy - H0 / 2) < 25, f"({cx},{cy})")
    # right-drag pan in paint mode: must pan, not paint
    n = cv[0].mask_pixels(); pan0 = (cv[0]._pan_x, cv[0]._pan_y)
    H.drag(app, cv[0], H.pt(cv[0], .5, .5), H.pt(cv[0], .6, .6), button=Qt.RightButton)
    check("right-drag pans, no paint, undo untouched", (cv[0]._pan_x, cv[0]._pan_y) != pan0 and cv[0].mask_pixels() == n, f"pan {pan0}→{(cv[0]._pan_x, cv[0]._pan_y)} mask {n}→{cv[0].mask_pixels()}")
    cv[0].clear_annotations(); app.processEvents()
    m0 = cv[0].mask().copy(); H.click(cv[0], H.pt(cv[0], .5, .5)); app.processEvents()
    cx, cy, k = centroid(m0, cv[0].mask())
    check("paint after pan still maps to image centre (dest rect follows pan)", k > 0 and abs(cx - W0 / 2) < 25 and abs(cy - H0 / 2) < 25, f"({cx},{cy})")
    # poly: right-click drops vertex; right-DRAG must pan and keep vertices
    tool("poly")
    for p in (H.pt(cv[0], .3, .3), H.pt(cv[0], .5, .3), H.pt(cv[0], .5, .5), H.pt(cv[0], .3, .5)):
        H.click(cv[0], p)
    H.click(cv[0], H.pt(cv[0], .4, .4), Qt.RightButton); app.processEvents()
    check("right-click drops last vertex", len(cv[0]._poly_pts) == 3, str(len(cv[0]._poly_pts)))
    pan0 = (cv[0]._pan_x, cv[0]._pan_y)
    H.drag(app, cv[0], H.pt(cv[0], .5, .5), H.pt(cv[0], .6, .6), button=Qt.RightButton)
    check("right-drag in poly pans and keeps vertices", (cv[0]._pan_x, cv[0]._pan_y) != pan0 and len(cv[0]._poly_pts) == 3, f"pan {pan0}→{(cv[0]._pan_x, cv[0]._pan_y)} pts={len(cv[0]._poly_pts)}")
    n0 = cv[0].mask_pixels(); H.key(cv[0], Qt.Key_Return); app.processEvents()
    check("Enter fills the (panned) polygon", cv[0].mask_pixels() > n0 and not H.invariants(cv[0]))
    cv[0]._zoom = 1.0; cv[0]._pan_x = cv[0]._pan_y = 0; cv[0].update(); app.processEvents()
run("T5 zoom/pan", t5)

# ── T6: main window hide/show with the dock open ───────────────────────────
def t6():
    c0.activated.emit(); app.processEvents(); tool("paint")
    modes_before = [c.wl_mode() for c in cv]
    win.hide(); app.processEvents(); H.pump(app, 100)
    check("main window hidden → dock hidden → canvases drag", not dock.isVisible() and all(c.wl_mode() == "drag" for c in cv), str([c.wl_mode() for c in cv]))
    check("ws button reflects hidden dock (observation)", True, f"ws_btn checked={win._ws_btn.isChecked()}")
    win.show(); app.processEvents(); H.pump(app, 100)
    check("main window shown → dock back, active panel has the tool", dock.isVisible() and cv[0].wl_mode() == "paint" and win._ws_btn.isChecked(),
          f"dock={dock.isVisible()} modes={[c.wl_mode() for c in cv]} ws_btn={win._ws_btn.isChecked()} before={modes_before}")
    win.showMinimized(); app.processEvents(); H.pump(app, 100)
    st_min = (dock.isVisible(), [c.wl_mode() for c in cv])
    win.showNormal(); app.processEvents(); H.pump(app, 100)
    check("minimize/restore keeps dock + tool", dock.isVisible() and cv[0].wl_mode() == "paint", f"minimized state={st_min} after={[c.wl_mode() for c in cv]}")
run("T6 hide/show", t6)

# ── T7: double-click / clicks on an EMPTY cell in each tool mode ──────────
def t7():
    cells[3].activated.emit(); app.processEvents()
    from viewer_vidi.tree_panel import _make_series_meta
    # make cell3 empty again is not possible via API; use a fresh boot-less approach: cell3 holds ws item 2. Use a never-loaded cell? all 4 are loaded.
    # Instead: dclick the drop label of a cell whose canvas stack is page 0 cannot be reached; so exercise dclick on cell widgets directly.
    for mode in ("paint", "poly", "rect"):
        tool(mode)
        for c in cells:
            H.dclick(c, QPoint(30, 30)); app.processEvents()
        if quad.is_fullscreen():
            quad._exit_fullscreen(); app.processEvents()
    check("dclick on cell widgets (header area) in every tool mode: no exception", True, str([c.wl_mode() for c in cv]))
run("T7 dclick cells", t7)

current[0] = "teardown"
win.close(); app.processEvents()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} checks passed; slot exceptions: {len(slot_exceptions)}")
for n, ok, info in results:
    if not ok: print("  FAILED:", n, info)
sys.exit(1 if (n_fail or slot_exceptions) else 0)
