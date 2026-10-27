"""Multipanel lens: multi-panel interplay + pre-existing per-cell controls (offscreen)."""
import os, sys, time, shutil, traceback
os.environ["QT_QPA_PLATFORM"] = "offscreen"
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB)
import harness as H
import numpy as np

D     = STAB + "/multipanel"
WS    = D + "/ws"       # 3 CR DICOMs (2044x1514)
WS2   = D + "/ws2"      # 2 CR DICOMs same patient → loads as a 2D-T series (TC buttons visible)
MR3D  = D + "/mr3d"     # 20 MR slices → 3-D series
OUT   = "vidi_output"

results = []
slot_exceptions = []   # (scenario, traceback text) — raised inside Qt slots
current = ["setup"]

def check(name, cond, info=""):
    results.append((current[0] + " | " + name, bool(cond), info))
    print(("PASS " if cond else "FAIL ") + current[0] + " | " + name + (f"  [{info}]" if info else ""), flush=True)

def _hook(et, ev, tb):
    txt = "".join(traceback.format_exception(et, ev, tb))
    slot_exceptions.append((current[0], txt))
    print(f"SLOT-EXCEPTION in {current[0]}:\n{txt}", flush=True)
sys.excepthook = _hook

from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QImage
app, win = H.boot()
from viewer_vidi.tree_panel import _make_series_meta
dock, quad = win._dock, win._quad
c0, c1 = quad.cell_at(0), quad.cell_at(1)
cv0, cv1 = c0.canvas(), c1.canvas()

def shortcut(k, mods):
    """QShortcut needs an active window; offscreen drops it after a modal dialog."""
    app.setActiveWindow(win); win.activateWindow(); app.processEvents()
    H.key(win, k, mods); app.processEvents()

def tool(mode):
    dock._tool_btns[mode].setChecked(True); dock._apply_tool(); app.processEvents()

def centroid(mask_before, mask_after):
    d = (mask_after > 0) & ~(mask_before > 0)
    ys, xs = np.nonzero(d)
    return (float(xs.mean()), float(ys.mean()), int(d.sum())) if d.size and d.any() else (None, None, 0)

def grab_rgb(canvas):
    """Rendered canvas as (H, W, 3) uint8 — what the user sees."""
    img = canvas.grab().toImage().convertToFormat(QImage.Format_RGB888)
    w, h = img.width(), img.height()
    ptr = img.constBits(); ptr.setsize(img.sizeInBytes())
    arr = np.frombuffer(ptr, np.uint8).reshape(h, img.bytesPerLine())[:, :w * 3].reshape(h, w, 3)
    return arr.copy()

def red_overlay_px(canvas):
    a = grab_rgb(canvas).astype(int)
    return int(((a[..., 0] - a[..., 1] > 40) & (a[..., 0] - a[..., 2] > 40)).sum())

def yellow_px(canvas):
    a = grab_rgb(canvas).astype(int)
    return int(((a[..., 0] > 180) & (a[..., 1] > 150) & (a[..., 2] < 120)).sum())

def run(name, fn):
    current[0] = name
    try:
        fn()
    except Exception:
        check("no python exception", False, traceback.format_exc().strip().splitlines()[-1])
        print(traceback.format_exc())

shutil.rmtree(os.path.join(WS, OUT), ignore_errors=True)
ws = H.open_workspace(app, win, WS, out_dir=OUT)
check("workspace opened, item 0 in cell 0 with brush", quad.active_cell() is c0 and c0.series_data() is not None
      and cv0.wl_mode() == "paint" and dock._index == 0, f"mode={cv0.wl_mode()} idx={dock._index}")
H0, W0 = cv0.displayed_pixels().shape
item_paths = [it.path for it in ws.items]

# ── S1: empty cell 1 becomes active, every tool used on the EMPTY canvas ───
def s1():
    c1.activated.emit(); app.processEvents()
    check("cell1 active", quad.active_cell() is c1)
    check("empty canvas got the brush tool", cv1.wl_mode() == "paint", cv1.wl_mode())
    check("cell0 canvas keeps paint mode (observation)", cv0.wl_mode() == "paint", cv0.wl_mode())
    check("stats label follows empty cell", dock._stats_lbl.text() == "mask 0 px · no rectangle", dock._stats_lbl.text())
    H.drag(app, cv1, H.pt(cv1, .3, .3), H.pt(cv1, .6, .4))
    check("paint drag on empty: mask None, invariants", cv1.mask() is None and cv1.mask_pixels() == 0 and not H.invariants(cv1), str(H.invariants(cv1)))
    tool("poly")
    for p in (H.pt(cv1, .2, .6), H.pt(cv1, .5, .6), H.pt(cv1, .5, .9)):
        H.click(cv1, p)
    H.click(cv1, H.pt(cv1, .5, .9), Qt.RightButton)
    H.dclick(cv1, H.pt(cv1, .2, .9)); app.processEvents()
    H.key(cv1, Qt.Key_Return); H.key(cv1, Qt.Key_Escape); app.processEvents()
    check("poly on empty: no vertices stored, no fullscreen, no mask", cv1._poly_pts == [] and not quad.is_fullscreen() and cv1.mask() is None,
          f"pts={cv1._poly_pts} fs={quad.is_fullscreen()}")
    tool("rect")
    H.drag(app, cv1, H.pt(cv1, .1, .1), H.pt(cv1, .7, .8))
    check("rect on empty: no crop rect", cv1.crop_rect() is None and not H.invariants(cv1))
    dock._clear_btn.click(); app.processEvents()
    dock._undo_btn.click(); app.processEvents()
    check("clear/undo on empty: 'Nothing to undo.'", dock._status_lbl.text() == "Nothing to undo.", dock._status_lbl.text())
    shortcut(Qt.Key_Z, Qt.ControlModifier)
    dock._refresh_stats()
    check("stats after clear/undo on empty", dock._stats_lbl.text() == "mask 0 px · no rectangle", dock._stats_lbl.text())
    dock._brush_spin.setValue(35); dock._erase_chk.setChecked(True); dock._erase_chk.setChecked(False); app.processEvents()
    check("brush spin / erase on empty canvas ok", cv1._brush_r == 35)
    dock._save(advance=False); app.processEvents()
    check("Save with EMPTY active panel refuses (status text)", not ws.items[0].done, dock._status_lbl.text())
    check("Save-on-empty message is accurate (observation)", "loading" not in dock._status_lbl.text().lower(), dock._status_lbl.text())
    # mouse-press activation path on the empty cell widget itself
    c0.activated.emit(); app.processEvents()
    H.press(c1, QPoint(40, 40)); H.release(c1, QPoint(40, 40)); app.processEvents()
    check("mouse press on empty cell activates it", quad.active_cell() is c1)
    tool("paint")
run("S1 empty-cell tools", s1)

# ── S2: load a different (3-D MR) series into cell 1, draw, switch back ───
def s2():
    c1.activated.emit(); app.processEvents()
    ok = H.load_file(app, c1, MR3D)
    check("MR 3-D series loaded in cell1", ok and c1.series_data() is not None, str(c1.series_data().series_type if c1.series_data() else None))
    # load_meta resets the canvas to drag — this is the tree/drop path, not the dock's
    check("after load_file into ACTIVE cell canvas mode (observation)", True, f"mode={cv1.wl_mode()} dock_tool={dock._current_tool()}")
    tool("paint")
    H1, W1 = cv1.displayed_pixels().shape
    check("cell1 mask has MR shape, differs from cell0", cv1.mask().shape == (H1, W1) and (H1, W1) != (H0, W0), f"{(H1, W1)} vs {(H0, W0)}")
    H.drag(app, cv1, H.pt(cv1, .3, .3), H.pt(cv1, .6, .3))
    n1 = cv1.mask_pixels()
    check("brush paints on cell1", n1 > 0, str(n1))
    check("stats show cell1 count", dock._stats_lbl.text().startswith(f"mask {n1:,} px"), dock._stats_lbl.text())
    check("cell0 mask untouched", cv0.mask_pixels() == 0)
    tool("rect")
    H.drag(app, cv1, H.pt(cv1, .2, .2), H.pt(cv1, .8, .9))
    r1 = cv1.crop_rect()
    check("rect on cell1", r1 is not None and not H.invariants(cv1), str(r1))
    # back to cell 0 via a real mouse press on its canvas (paint mode → one brush dot)
    tool("paint")
    H.click(cv0, H.pt(cv0, .5, .5)); app.processEvents()
    check("press on cell0 canvas activates cell0", quad.active_cell() is c0)
    n0 = cv0.mask_pixels()
    check("the activating click painted a brush dot on cell0 (observation)", True, f"{n0} px")
    check("stats follow cell0", dock._stats_lbl.text() == f"mask {n0:,} px · no rectangle", dock._stats_lbl.text())
    check("cell1 mask/rect independent", cv1.mask_pixels() == n1 and cv1.crop_rect() == r1)
    check("invariants both", not H.invariants(cv0) and not H.invariants(cv1))
    c1.activated.emit(); app.processEvents()
    check("stats follow cell1 again", dock._stats_lbl.text().startswith(f"mask {n1:,} px · rect"), dock._stats_lbl.text())
run("S2 two panels", s2)

# ── S3: Save with cell 1 (other series) active → Panel mismatch ────────────
def s3():
    c1.activated.emit(); app.processEvents()
    seen = H.auto_close_dialogs(app, 200)
    dock._save(advance=False); app.processEvents(); H.pump(app, 400)
    check("Panel mismatch dialog", seen and seen[0][1] == "Panel mismatch", str(seen))
    check("item not marked done, no output dir", not ws.items[0].done and not os.path.isdir(os.path.join(WS, OUT)))
    seen2 = H.auto_close_dialogs(app, 200)
    check("activeWindow after modal dialog (observation)", True, str(app.activeWindow())); shortcut(Qt.Key_S, Qt.ControlModifier); H.pump(app, 400)
    check("Ctrl+S with cell1 active also refuses", seen2 and seen2[0][1] == "Panel mismatch" and dock._index == 0, str(seen2))
    # Next with cell 1 active loads item 1 INTO cell 1 (active panel), cell 0 keeps item 0
    dock._next_btn.click(); app.processEvents()
    H.wait_loaded(app, c1)
    check("Next loads into active cell1", os.path.abspath(c1.series_data().meta.series_dir) == item_paths[1] and dock._index == 1)
    check("cell0 still shows item 0 with its mask", os.path.abspath(c0.series_data().meta.series_dir) == item_paths[0] and cv0.mask_pixels() > 0)
    check("cell1 tool re-applied after dock load", cv1.wl_mode() == "paint", cv1.wl_mode())
    check("cell1 fresh mask after load", cv1.mask_pixels() == 0 and cv1.crop_rect() is None)
    # cell0 active again → Save must refuse (shows item 0, current is item 1)
    c0.activated.emit(); app.processEvents()
    seen3 = H.auto_close_dialogs(app, 200)
    dock._save(advance=False); app.processEvents(); H.pump(app, 400)
    check("Save with cell0 (item 0) while current item 1 → mismatch", seen3 and seen3[0][1] == "Panel mismatch", str(seen3))
run("S3 mismatch", s3)

# ── S4: tree-path / drop-path load into the ACTIVE cell while dock open ─────
def s4():
    c0.activated.emit(); app.processEvents()
    tool("paint")
    meta = _make_series_meta(item_paths[2])
    win._on_series_selected(meta)          # what the left tree does on double-click
    H.wait_loaded(app, c0)
    check("tree-path load into active cell: canvas mode vs dock tool", cv0.wl_mode() == dock._current_tool(),
          f"canvas={cv0.wl_mode()} dock={dock._current_tool()}")
    tool("paint")
    c0.load_meta(meta); c0.activated.emit()   # what dropEvent does
    H.wait_loaded(app, c0)
    check("drop-path load into active cell: canvas mode vs dock tool", cv0.wl_mode() == dock._current_tool(),
          f"canvas={cv0.wl_mode()} dock={dock._current_tool()}")
    tool("paint")
run("S4 tree/drop load", s4)

# ── S5: fullscreen toggle by double-click in each mode ─────────────────────
def s5():
    # fresh state: reopen workspace → item 1 pending? (item 0/1 not done) → index 0 into active cell
    c0.activated.emit(); app.processEvents()
    H.open_workspace(app, win, WS, out_dir=OUT)
    H.wait_loaded(app, c0)
    for mode in ("drag", "paint", "rect"):
        tool(mode)
        before = cv0.mask_pixels(); rect_before = cv0.crop_rect()
        H.dclick(cv0, H.pt(cv0, .5, .5)); app.processEvents()
        fs = quad.is_fullscreen()
        H.dclick(cv0, H.pt(cv0, .5, .5)); app.processEvents()
        check(f"dclick in {mode} toggles fullscreen on/off", fs and not quad.is_fullscreen(), f"on={fs} off={not quad.is_fullscreen()}")
        check(f"dclick in {mode}: crop rect unchanged, invariants", cv0.crop_rect() == rect_before and not H.invariants(cv0))
        if mode == "paint":
            check("dclick in paint mode paints brush dots (observation)", True, f"{cv0.mask_pixels() - before} px added by 2 double-clicks")
        check(f"canvas mode after fullscreen round-trip ({mode})", cv0.wl_mode() == mode, cv0.wl_mode())
    # roi via the cell header button
    tool("drag"); c0._roi_btn.setChecked(True); app.processEvents()
    check("ROI button → canvas roi", cv0.wl_mode() == "roi")
    H.dclick(cv0, H.pt(cv0, .5, .5)); app.processEvents(); fs = quad.is_fullscreen()
    H.dclick(cv0, H.pt(cv0, .5, .5)); app.processEvents()
    check("dclick in roi toggles fullscreen", fs and not quad.is_fullscreen())
    c0._roi_btn.setChecked(False); app.processEvents()
    tool("poly")
    for p in (H.pt(cv0, .2, .2), H.pt(cv0, .4, .2), H.pt(cv0, .4, .4)):
        H.click(cv0, p)
    H.dclick(cv0, H.pt(cv0, .2, .4)); app.processEvents()
    check("dclick in poly: no fullscreen, polygon filled", not quad.is_fullscreen() and cv0.mask_pixels() > 0.8 * (0.2 * W0) * (0.2 * H0), str(cv0.mask_pixels()))
    # programmatic fullscreen then painting: geometry recomputed?
    tool("paint"); dock._brush_spin.setValue(20)
    r_before = cv0._dest_rect()
    quad._toggle_fullscreen(c0); app.processEvents(); H.pump(app, 100)
    r_fs = cv0._dest_rect()
    check("fullscreen enlarges the dest rect", quad.is_fullscreen() and r_fs.width() > r_before.width(), f"{r_before.width()} → {r_fs.width()}")
    check("fullscreen enter re-applies tool (set_active emits)", cv0.wl_mode() == "paint")
    dock._clear_btn.click(); app.processEvents()
    m0 = cv0.mask().copy()
    H.click(cv0, H.pt(cv0, .5, .5)); app.processEvents()
    cx, cy, n = centroid(m0, cv0.mask())
    check("paint in fullscreen lands at image centre", n > 0 and abs(cx - W0 / 2) < 25 and abs(cy - H0 / 2) < 25, f"centroid=({cx},{cy}) n={n} expected ({W0/2},{H0/2})")
    m0 = cv0.mask().copy()
    H.click(cv0, H.pt(cv0, .25, .75)); app.processEvents()
    cx, cy, n = centroid(m0, cv0.mask())
    check("paint in fullscreen at (.25,.75)", n > 0 and abs(cx - W0 * .25) < 25 and abs(cy - H0 * .75) < 25, f"centroid=({cx},{cy})")
    tool("rect")
    H.drag(app, cv0, H.pt(cv0, .1, .1), H.pt(cv0, .6, .6))
    r = cv0.crop_rect()
    check("rect in fullscreen maps to image coords", r is not None and abs(r[0] - .1 * W0) < 10 and abs(r[2] - .6 * W0) < 10 and abs(r[3] - .6 * H0) < 10, str(r))
    n_fs = cv0.mask_pixels()
    quad._toggle_fullscreen(c0); app.processEvents(); H.pump(app, 100)
    check("exit fullscreen keeps mask + rect", not quad.is_fullscreen() and cv0.mask_pixels() == n_fs and cv0.crop_rect() == r and not H.invariants(cv0))
    tool("paint"); cv0.undo_annotation(); cv0.clear_annotations(); app.processEvents()
    m0 = cv0.mask().copy()
    H.click(cv0, H.pt(cv0, .5, .5)); app.processEvents()
    cx, cy, n = centroid(m0, cv0.mask())
    check("paint after exit lands at image centre", n > 0 and abs(cx - W0 / 2) < 25 and abs(cy - H0 / 2) < 25, f"centroid=({cx},{cy})")
run("S5 fullscreen", s5)

# ── S6: cell header buttons ROI / i / TC / ROI-TC while Brush is selected ───
def s6():
    c0.activated.emit(); app.processEvents(); tool("paint")
    dock._clear_btn.click(); app.processEvents()
    wl0 = cv0.wl()
    c0._roi_btn.click(); app.processEvents()
    check("ROI header button switches canvas to roi under the dock", cv0.wl_mode() == "roi" and c0._roi_btn.isChecked())
    check("dock still shows Brush while canvas is roi (observation)", True, f"dock tool={dock._current_tool()} canvas={cv0.wl_mode()}")
    H.drag(app, cv0, H.pt(cv0, .3, .3), H.pt(cv0, .6, .6))
    check("ROI drag sets W/L, paints nothing", cv0.wl() != wl0 and cv0.mask_pixels() == 0, f"wl {wl0}→{cv0.wl()} mask={cv0.mask_pixels()}")
    check("roi drag keeps cell active + roi mode", quad.active_cell() is c0 and cv0.wl_mode() == "roi", cv0.wl_mode())
    c0._roi_btn.click(); app.processEvents()
    check("un-ROI → canvas 'drag' although dock shows Brush", cv0.wl_mode() == "drag" and dock._current_tool() == "paint", cv0.wl_mode())
    wl1 = cv0.wl()
    H.drag(app, cv0, H.pt(cv0, .3, .3), H.pt(cv0, .6, .6))
    check("drag after un-ROI changes W/L instead of painting", cv0.wl() != wl1 and cv0.mask_pixels() == 0, f"mask={cv0.mask_pixels()} mode={cv0.wl_mode()}")
    # clicking Brush again in the dock while the ROI button is checked
    c0._roi_btn.click(); app.processEvents()
    dock._tool_btns["paint"].click(); app.processEvents()
    check("dock Brush click overrides canvas to paint; ROI button stays checked (observation)", cv0.wl_mode() == "paint", f"roi_btn={c0._roi_btn.isChecked()} mode={cv0.wl_mode()}")
    H.drag(app, cv0, H.pt(cv0, .3, .3), H.pt(cv0, .5, .3))
    check("paint works while ROI button is checked", cv0.mask_pixels() > 0, str(cv0.mask_pixels()))
    c0._roi_btn.click(); app.processEvents()
    check("unchecking stale ROI button kicks canvas back to drag (observation)", True, f"mode={cv0.wl_mode()}")
    # Next item restores Brush and clears the ROI button
    dock._next_btn.click(); H.wait_loaded(app, c0); app.processEvents()
    check("next item restores Brush, ROI button cleared", cv0.wl_mode() == "paint" and not c0._roi_btn.isChecked(), f"mode={cv0.wl_mode()} roi={c0._roi_btn.isChecked()}")
    # i button
    c0._info_btn.setChecked(True); app.processEvents()
    check("i button keeps paint mode, overlay on", cv0.wl_mode() == "paint" and cv0._overlay is not None)
    H.drag(app, cv0, H.pt(cv0, .4, .5), H.pt(cv0, .6, .5))
    check("painting with overlay on works", cv0.mask_pixels() > 0)
    c0._info_btn.setChecked(False); app.processEvents()
    # TC / ROI-TC on a 2D-T series in cell 1
    c1.activated.emit(); app.processEvents()
    ok = H.load_file(app, c1, WS2); tool("paint")
    st = c1.series_data().series_type.value if c1.series_data() else None
    check("ws2 loads as a time series in cell1", ok and st == "2D-T" and c1._tc_btn.isVisible(), f"type={st} tc_vis={c1._tc_btn.isVisible()}")
    if c1._tc_btn.isVisible():
        c1._tc_btn.click(); app.processEvents()
        check("TC button → canvas tc", cv1.wl_mode() == "tc")
        H.click(cv1, H.pt(cv1, .5, .5)); app.processEvents()
        check("TC click places a point, no paint", len(cv1.tc_points()) == 1 and cv1.mask_pixels() == 0, f"tc={cv1.tc_points()} mask={cv1.mask_pixels()}")
        c1._tc_btn.click(); app.processEvents()
        check("un-TC → drag (dock still Brush)", cv1.wl_mode() == "drag")
        c1._roi_tc_btn.click(); app.processEvents()
        check("ROI-TC button → canvas roi_tc", cv1.wl_mode() == "roi_tc")
        H.drag(app, cv1, H.pt(cv1, .3, .3), H.pt(cv1, .6, .6), steps=20)
        check("ROI-TC lasso: no mask paint", cv1.mask_pixels() == 0 and len(cv1._roi_tc_polys) >= 0, f"polys={len(cv1._roi_tc_polys)} mask={cv1.mask_pixels()}")
        c1._roi_tc_btn.click(); app.processEvents()
        tool("paint")
        H.drag(app, cv1, H.pt(cv1, .3, .3), H.pt(cv1, .6, .3))
        check("brush after TC/ROI-TC round trip paints, tc point kept", cv1.mask_pixels() > 0 and len(cv1.tc_points()) == 1 and not H.invariants(cv1))
    c0.activated.emit(); app.processEvents()
run("S6 header buttons", s6)

# ── S7: info-overlay header click in paint mode must not paint ─────────────
def s7():
    c0.activated.emit(); app.processEvents(); tool("paint")
    dock._clear_btn.click(); app.processEvents(); u0 = len(cv0._undo)
    c0._info_btn.setChecked(True); app.processEvents(); cv0.repaint(); app.processEvents()
    rects = list(cv0._ov_header_rects)
    if not rects:
        cv0.grab(); app.processEvents(); rects = list(cv0._ov_header_rects)
    check("overlay has clickable group headers", len(rects) > 0, str([(t, r.x(), r.y(), r.width(), r.height()) for r, t in rects]))
    if not rects:
        return
    r, title = rects[0]
    centre = r.center()
    H.click(cv0, centre); app.processEvents()
    check("click on collapsed header expands it without painting", title in cv0._ov_expanded and cv0.mask_pixels() == 0, f"expanded={cv0._ov_expanded} mask={cv0.mask_pixels()}")
    cv0.repaint(); app.processEvents(); cv0.grab()
    rects2 = list(cv0._ov_header_rects)
    r2 = next((rr for rr, t in rects2 if t == title), None)
    check("header rect updated after expand", r2 is not None and r2.y() <= r.y(), f"{r.y()} → {r2.y() if r2 else None}")
    if r2 is not None:
        # press on the header, drag away, release → must not paint
        H.drag(app, cv0, r2.center(), H.pt(cv0, .5, .5))
        check("press on expanded header + drag away paints nothing", cv0.mask_pixels() == 0 and title not in cv0._ov_expanded, f"mask={cv0.mask_pixels()} expanded={cv0._ov_expanded}")
    # click on a non-header spot in the overlay column (a detail line) → paints (expected: only headers are consumed)
    H.click(cv0, centre); app.processEvents()
    check("second header click after collapse: no paint, undo untouched", cv0.mask_pixels() == 0 and len(cv0._undo) == u0, f"mask={cv0.mask_pixels()} undo={len(cv0._undo)} (u0={u0}) expanded={cv0._ov_expanded}")
    # same in poly and rect mode
    cv0.repaint(); cv0.grab(); app.processEvents()
    r3 = next((rr for rr, t in cv0._ov_header_rects if t == title), None)
    tool("poly"); H.click(cv0, r3.center()); app.processEvents()
    check("header click in poly mode adds no vertex", cv0._poly_pts == [], str(cv0._poly_pts))
    cv0.repaint(); cv0.grab(); app.processEvents()
    r4 = next((rr for rr, t in cv0._ov_header_rects if t == title), None)
    tool("rect"); H.drag(app, cv0, r4.center(), H.pt(cv0, .3, .3))
    check("header press in rect mode starts no rectangle", cv0.crop_rect() is None, str(cv0.crop_rect()))
    c0._info_btn.setChecked(False); app.processEvents(); tool("paint")
run("S7 overlay header click", s7)

# ── S8: pressing I in annotation modes ─────────────────────────────────────
def s8():
    for mode in ("paint", "poly", "rect"):
        tool(mode)
        if mode == "poly":
            for p in (H.pt(cv0, .2, .2), H.pt(cv0, .4, .2), H.pt(cv0, .4, .4)):
                H.click(cv0, p)
        was = c0._info_btn.isChecked()
        H.key(cv0, Qt.Key_I); app.processEvents()
        check(f"I toggles overlay in {mode}, mode kept", c0._info_btn.isChecked() != was and cv0.wl_mode() == mode, f"info={c0._info_btn.isChecked()} mode={cv0.wl_mode()}")
        if mode == "poly":
            check("poly vertices survive I", len(cv0._poly_pts) == 3, str(cv0._poly_pts))
            n0 = cv0.mask_pixels(); H.key(cv0, Qt.Key_Return); app.processEvents()
            check("Enter fills polygon with overlay on", cv0.mask_pixels() > n0 and not H.invariants(cv0))
        H.key(cv0, Qt.Key_I); app.processEvents()
    check("overlay back off", not c0._info_btn.isChecked())
    tool("paint")
run("S8 I key", s8)

# ── S9: invert / colormap / Reset W/L keep mask overlay + crop rect ─────────
def s9():
    tool("paint"); dock._clear_btn.click(); app.processEvents()
    H.drag(app, cv0, H.pt(cv0, .3, .4), H.pt(cv0, .7, .4))
    tool("rect"); H.drag(app, cv0, H.pt(cv0, .2, .2), H.pt(cv0, .8, .8))
    n, r = cv0.mask_pixels(), cv0.crop_rect()
    red0, yel0 = red_overlay_px(cv0), yellow_px(cv0)
    check("baseline overlay visible (red mask px, yellow rect px)", red0 > 100 and yel0 > 50, f"red={red0} yellow={yel0}")
    shortcut(Qt.Key_I, Qt.ControlModifier)
    check("Ctrl+I inverted the active cell", cv0.invert() and win._invert_btn.isChecked())
    red1, yel1 = red_overlay_px(cv0), yellow_px(cv0)
    check("invert keeps mask + rect data", cv0.mask_pixels() == n and cv0.crop_rect() == r and cv0._mask_nonempty and not H.invariants(cv0))
    check("invert keeps overlay rendered", red1 > 100 and yel1 > 50, f"red={red1} yellow={yel1}")
    for cm in ("Hot", "Jet", "Gray"):
        if win._cmap_combo.findText(cm) >= 0:
            win._cmap_combo.setCurrentText(cm); app.processEvents()
            check(f"colormap {cm} keeps mask + rect", cv0.mask_pixels() == n and cv0.crop_rect() == r and not H.invariants(cv0))
    shortcut(Qt.Key_I, Qt.ControlModifier)
    check("Ctrl+I again un-inverts", not cv0.invert())
    H.drag(app, cv0, H.pt(cv0, .3, .3), H.pt(cv0, .6, .6))   # in rect mode: replace rect
    win._wc_spin.setValue(cv0.wl()[0] + 100); app.processEvents()
    check("toolbar W/L spin keeps mask + rect", cv0.mask_pixels() == n and cv0.crop_rect() is not None and not H.invariants(cv0))
    win._reset_wl(); app.processEvents()
    sd = c0.series_data()
    check("Reset W/L restores header W/L, keeps annotations", cv0.wl() == (sd.window_center, max(1.0, sd.window_width)) and cv0.mask_pixels() == n and not H.invariants(cv0), f"wl={cv0.wl()}")
    check("overlay still rendered after reset", red_overlay_px(cv0) > 100 and yellow_px(cv0) > 50)
    # invert on the non-active cell must not change
    inv1 = cv1.invert()
    shortcut(Qt.Key_I, Qt.ControlModifier)
    check("invert only touches active cell", cv1.invert() == inv1 and cv0.invert())
    shortcut(Qt.Key_I, Qt.ControlModifier)
run("S9 invert/cmap/reset", s9)

# ── S10: window resize with annotations ────────────────────────────────────
def s10():
    tool("paint"); dock._clear_btn.click(); app.processEvents(); dock._brush_spin.setValue(20)
    m0 = cv0.mask().copy(); H.click(cv0, H.pt(cv0, .25, .25)); app.processEvents()
    ca = centroid(m0, cv0.mask())
    tool("rect"); H.drag(app, cv0, H.pt(cv0, .2, .2), H.pt(cv0, .8, .8)); r = cv0.crop_rect()
    rect_before = cv0._dest_rect()
    win.resize(900, 600); app.processEvents(); H.pump(app, 150)
    rect_after = cv0._dest_rect()
    check("resize changes dest rect", rect_after != rect_before, f"{rect_before} → {rect_after}")
    check("resize keeps mask/rect, invariants", cv0.mask_pixels() == ca[2] and cv0.crop_rect() == r and not H.invariants(cv0))
    check("overlay rendered after resize", red_overlay_px(cv0) > 50 and yellow_px(cv0) > 30, f"red={red_overlay_px(cv0)} yel={yellow_px(cv0)}")
    tool("paint"); cv0.undo_annotation(); dock._clear_btn.click(); app.processEvents()
    m0 = cv0.mask().copy(); H.click(cv0, H.pt(cv0, .25, .25)); app.processEvents()
    cb = centroid(m0, cv0.mask())
    tol = 2 * W0 / max(1, rect_after.width()) + 1   # 2 screen px of int() quantisation
    check("same fractional click maps to same image px after resize", cb[2] > 0 and ca[0] is not None and abs(ca[0] - cb[0]) < tol and abs(ca[1] - cb[1]) < tol, f"before={ca} after={cb} tol={tol:.1f}")
    win.resize(1400, 900); app.processEvents(); H.pump(app, 150)
    dock._clear_btn.click(); app.processEvents()
    m0 = cv0.mask().copy(); H.click(cv0, H.pt(cv0, .75, .75)); app.processEvents()
    cc = centroid(m0, cv0.mask())
    check("after resize back: (.75,.75) maps right", cc[2] > 0 and abs(cc[0] - .75 * W0) < 10 and abs(cc[1] - .75 * H0) < 10, f"{cc}")
run("S10 resize", s10)

# ── S11: dock moved to the left area ───────────────────────────────────────
def s11():
    tool("paint")
    n = cv0.mask_pixels(); r = cv0.crop_rect()
    win.addDockWidget(Qt.LeftDockWidgetArea, dock); app.processEvents(); H.pump(app, 150)
    check("dock now in left area and visible", win.dockWidgetArea(dock) == Qt.LeftDockWidgetArea and dock.isVisible())
    check("tool survives the move on active cell", cv0.wl_mode() == "paint", cv0.wl_mode())
    check("annotations survive the move", cv0.mask_pixels() == n and cv0.crop_rect() == r)
    check("non-active cell mode after move (observation)", True, f"cv1 mode={cv1.wl_mode()}")
    m0 = cv0.mask().copy(); H.click(cv0, H.pt(cv0, .5, .5)); app.processEvents()
    cx, cy, k = centroid(m0, cv0.mask())
    check("paint after move maps to centre", k > 0 and abs(cx - W0 / 2) < 25 and abs(cy - H0 / 2) < 25, f"({cx},{cy})")
    win.addDockWidget(Qt.RightDockWidgetArea, dock); app.processEvents(); H.pump(app, 150)
    check("back to right area, still paint", win.dockWidgetArea(dock) == Qt.RightDockWidgetArea and cv0.wl_mode() == "paint" and dock.isVisible())
    dock.setFloating(True); app.processEvents(); H.pump(app, 150)
    check("floating dock keeps tool", dock.isVisible() and cv0.wl_mode() == "paint", f"vis={dock.isVisible()} mode={cv0.wl_mode()}")
    dock.setFloating(False); app.processEvents(); H.pump(app, 150)
    check("re-docked keeps tool", dock.isVisible() and cv0.wl_mode() == "paint")
run("S11 dock left", s11)

# ── S12: sidebar hidden (Ctrl+B) ───────────────────────────────────────────
def s12():
    tool("paint")
    rb = cv0._dest_rect()
    shortcut(Qt.Key_B, Qt.ControlModifier); H.pump(app, 150)
    check("Ctrl+B hides the tree", not win._tree.isVisible())
    check("canvas grew", cv0._dest_rect().width() >= rb.width(), f"{rb.width()} → {cv0._dest_rect().width()}")
    dock._clear_btn.click(); app.processEvents()
    m0 = cv0.mask().copy(); H.click(cv0, H.pt(cv0, .5, .5)); app.processEvents()
    cx, cy, k = centroid(m0, cv0.mask())
    check("paint with sidebar hidden maps to centre", k > 0 and abs(cx - W0 / 2) < 25 and abs(cy - H0 / 2) < 25, f"({cx},{cy})")
    check("dock still visible + paint", dock.isVisible() and cv0.wl_mode() == "paint")
    shortcut(Qt.Key_B, Qt.ControlModifier); H.pump(app, 150)
    check("Ctrl+B restores the tree", win._tree.isVisible())
run("S12 sidebar", s12)

# ── S13: Save from the (left/right) dock with matching panel → files written ─
def s13():
    c0.activated.emit(); app.processEvents()
    it = dock._ws.items[dock._index]
    shown = os.path.abspath(c0.series_data().meta.series_dir)
    check("active panel shows current item", shown == it.path, f"{shown} vs {it.path}")
    for k in dock._fmt_chk.values(): k.setChecked(False)
    dock._fmt_chk["png"].setChecked(True)
    seen = H.auto_close_dialogs(app, 300)
    dock._save(advance=False); app.processEvents(); H.pump(app, 400)
    p = os.path.join(WS, OUT, "png", f"{it.stem}_mask.png")
    check("Save with matching panel writes mask png, no dialog", os.path.isfile(p) and not seen and it.done, f"{dock._status_lbl.text()} dialogs={seen}")
run("S13 save ok", s13)

# ── S14: Ctrl+S while the dock is hidden ───────────────────────────────────
def s14():
    tool("paint"); dock._clear_btn.click(); app.processEvents()
    H.drag(app, cv0, H.pt(cv0, .3, .3), H.pt(cv0, .6, .3))
    idx = dock._index; dock._status_lbl.setText("")
    win._ws_btn.setChecked(False); app.processEvents()
    check("dock hidden → all canvases drag", not dock.isVisible() and all(c.canvas().wl_mode() == "drag" for c in quad.cells()))
    shortcut(Qt.Key_S, Qt.ControlModifier); H.wait_loaded(app, c0)
    check("Ctrl+S with dock hidden: saved+advanced? (observation)", True, f"idx {idx}→{dock._index} status='{dock._status_lbl.text()}'")
    check("canvas mode after hidden-dock Ctrl+S advance stays drag", cv0.wl_mode() == "drag", f"mode={cv0.wl_mode()} dock_visible={dock.isVisible()}")
    win._ws_btn.setChecked(True); app.processEvents()
run("S14 hidden-dock Ctrl+S", s14)

current[0] = "teardown"
win.close(); app.processEvents()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} checks passed; slot exceptions: {len(slot_exceptions)}")
for n, ok, info in results:
    if not ok:
        print("  FAILED:", n, info)
sys.exit(1 if (n_fail or slot_exceptions) else 0)
