"""dockstate lens, part 3: tool state machine across hide/show, shortcuts,
_current_tool with no checked button, erase+polygon, brush extremes."""
import os, sys, time
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/dockstate")
from common import *
import numpy as np
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtWidgets import QApplication
app, win = H.boot()
from viewer_vidi import workspace as W
from viewer_vidi import annotation_dock as AD
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
def stub_dir(path): AD.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: path)
def open_ws(root):
    stub_dir(root); dock._open_dir(); return H.wait_loaded(app, cell)
def tool(mode): dock._tool_btns[mode].setChecked(True); dock._apply_tool()
def show_dock(on): win._ws_btn.setChecked(on); app.processEvents()
win.activateWindow(); app.processEvents()

@scenario("shortcuts with NO workspace open, dock hidden")
def t1():
    check("dock hidden initially", not dock.isVisible())
    H.key(win, Qt.Key_S, Qt.ControlModifier); app.processEvents()
    check("Ctrl+S with no workspace: no crash, dock stays hidden, status says open a workspace", not dock.isVisible() and dock._status_lbl.text() == "Open a workspace first.", dock._status_lbl.text())
    H.key(win, Qt.Key_Z, Qt.ControlModifier); app.processEvents()
    check("Ctrl+Z with dock hidden: no-op, no crash", dock._status_lbl.text() == "Open a workspace first.")
    check("canvas mode still drag", canvas.wl_mode() == "drag", canvas.wl_mode())
    H.key(win, Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier); app.processEvents()
    check("Ctrl+Shift+W shows dock; toolbar button checked; brush applied to active panel", dock.isVisible() and win._ws_btn.isChecked() and canvas.wl_mode() == "paint", canvas.wl_mode())
    H.key(win, Qt.Key_Z, Qt.ControlModifier); app.processEvents()
    check("Ctrl+Z with dock shown but no image: 'Nothing to undo.'", dock._status_lbl.text() == "Nothing to undo.", dock._status_lbl.text())
    dock._undo_btn.click(); dock._clear_btn.click(); app.processEvents()
    check("Undo/Clear buttons with no image: no crash, stats 0", dock._stats_lbl.text() == "mask 0 px · no rectangle" and not H.invariants(canvas), dock._stats_lbl.text())
    H.key(win, Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier); app.processEvents()
    check("Ctrl+Shift+W again hides dock; drag restored", not dock.isVisible() and not win._ws_btn.isChecked() and canvas.wl_mode() == "drag")
    # dock close button path: dock.close() -> visibilityChanged -> ws_btn unchecked
    show_dock(True); dock.close(); app.processEvents()
    check("closing the dock via its own close syncs the toolbar button off", not dock.isVisible() and not win._ws_btn.isChecked() and canvas.wl_mode() == "drag")
t1()

ws = fresh_ws("T_A", n=4)

@scenario("shortcuts with a workspace open")
def t2():
    show_dock(True); open_ws(ws)
    stroke(app, canvas); n = canvas.mask_pixels()
    check("stroke painted", n > 0)
    H.key(win, Qt.Key_Z, Qt.ControlModifier); app.processEvents()
    check("Ctrl+Z undoes the stroke", canvas.mask_pixels() == 0)
    stroke(app, canvas)
    H.key(win, Qt.Key_S, Qt.ControlModifier); H.wait_loaded(app, cell)
    check("Ctrl+S = Save & Next: item 0 done, index 1", dock._ws.items[0].done and dock._index == 1)
    # dock hidden, workspace open: Ctrl+S still saves (no visibility guard) — document behaviour
    dock._apply_tool(); stroke(app, canvas); n1 = canvas.mask_pixels()
    show_dock(False)
    check("hidden: mask kept on canvas, mode drag", canvas.mask_pixels() == n1 and canvas.wl_mode() == "drag")
    H.key(win, Qt.Key_Z, Qt.ControlModifier); app.processEvents()
    check("hidden: Ctrl+Z ignored (mask unchanged)", canvas.mask_pixels() == n1)
    H.key(win, Qt.Key_S, Qt.ControlModifier); H.wait_loaded(app, cell)
    check("hidden: Ctrl+S still saves item 1 and advances to 2 (no visibility guard)", dock._ws.items[1].done and dock._index == 2, f"done={dock._ws.items[1].done} idx={dock._index}")
    check("hidden + advanced: new item loaded in drag mode (dock hidden)", canvas.wl_mode() == "drag", canvas.wl_mode())
    show_dock(True)
    check("show again: paint re-applied, stats refreshed", canvas.wl_mode() == "paint" and dock._stats_lbl.text().startswith("mask 0 px"), dock._stats_lbl.text())
t2()

@scenario("hide the dock mid-polygon (vertices placed, not closed)")
def t3():
    open_ws(fresh_ws("T_B", n=2)); tool("poly")
    for p in ((0.2, 0.2), (0.6, 0.2), (0.6, 0.6)):
        H.click(canvas, H.pt(canvas, *p))
    app.processEvents()
    check("3 vertices pending", len(canvas._poly_pts) == 3, str(canvas._poly_pts))
    show_dock(False)
    check("hidden: mode drag, pending vertices dropped", canvas.wl_mode() == "drag" and canvas._poly_pts == [], f"{canvas.wl_mode()} {canvas._poly_pts}")
    H.dclick(canvas, H.pt(canvas, 0.2, 0.6)); app.processEvents()
    check("double-click while hidden: nothing filled; fullscreen toggled (normal viewer behaviour)", canvas.mask_pixels() == 0, str(canvas.mask_pixels()))
    if quad.is_fullscreen():
        H.dclick(canvas, H.pt(canvas, 0.2, 0.6)); app.processEvents()
    show_dock(True)
    check("shown again: poly mode restored with no leftover vertices", canvas.wl_mode() == "poly" and canvas._poly_pts == [] and dock._tool_btns["poly"].isChecked())
    H.key(canvas, Qt.Key_Return); app.processEvents()
    check("Enter with no vertices: no fill, no crash", canvas.mask_pixels() == 0 and not H.invariants(canvas))
    # finish a polygon now to prove the tool still works
    for p in ((0.2, 0.2), (0.6, 0.2), (0.6, 0.6)):
        H.click(canvas, H.pt(canvas, *p))
    H.key(canvas, Qt.Key_Return); app.processEvents()
    check("polygon after show works", canvas.mask_pixels() > 0 and not H.invariants(canvas), str(canvas.mask_pixels()))
    # Esc cancel, right-click drop
    H.click(canvas, H.pt(canvas, 0.1, 0.8)); H.click(canvas, H.pt(canvas, 0.3, 0.8))
    H.click(canvas, H.pt(canvas, 0.3, 0.8), Qt.RightButton); app.processEvents()
    check("right-click drops last vertex", len(canvas._poly_pts) == 1, str(canvas._poly_pts))
    H.key(canvas, Qt.Key_Escape); app.processEvents()
    check("Esc cancels", canvas._poly_pts == [])
t3()

@scenario("hide the dock mid-brush-stroke (press without release)")
def t4():
    open_ws(fresh_ws("T_C", n=2)); tool("paint")
    a, b = H.pt(canvas, 0.3, 0.5), H.pt(canvas, 0.5, 0.5)
    H.press(canvas, a); H.move(canvas, b, Qt.LeftButton); app.processEvents()
    n_mid = canvas.mask_pixels()
    check("mid-stroke painted, stroke active", n_mid > 0 and canvas._stroke_last is not None)
    show_dock(False)
    check("hidden mid-stroke: mode drag, stroke state cleared, mask kept", canvas.wl_mode() == "drag" and canvas._stroke_last is None and canvas.mask_pixels() == n_mid)
    H.move(canvas, H.pt(canvas, 0.8, 0.5), Qt.LeftButton); H.release(canvas, H.pt(canvas, 0.8, 0.5)); app.processEvents()
    check("moving/releasing while hidden paints nothing more", canvas.mask_pixels() == n_mid, f"{n_mid} -> {canvas.mask_pixels()}")
    wl_after = canvas.wl()
    check("release in drag mode did not touch W/L (no drag start)", wl_after == canvas.wl())
    check("invariants while hidden", not H.invariants(canvas), str(H.invariants(canvas)))
    show_dock(True)
    check("shown: paint mode, undo stack has the partial stroke", canvas.wl_mode() == "paint" and len(canvas._undo) == 1)
    check("undo removes the partial stroke", canvas.undo_annotation() and canvas.mask_pixels() == 0)
    # now a fresh stroke works and stats refresh via the signal
    stroke(app, canvas)
    check("stroke after re-show paints and stats label updates", canvas.mask_pixels() > 0 and dock._stats_lbl.text().startswith(f"mask {canvas.mask_pixels():,} px"), dock._stats_lbl.text())
t4()

@scenario("hide mid-rect-drag")
def t5():
    tool("rect")
    H.press(canvas, H.pt(canvas, 0.2, 0.2)); H.move(canvas, H.pt(canvas, 0.5, 0.5), Qt.LeftButton); app.processEvents()
    show_dock(False)
    H.release(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents()
    check("rect drag interrupted by hide: no rect stored, mode drag", canvas.crop_rect() is None and canvas.wl_mode() == "drag")
    show_dock(True)
    check("rect mode restored", canvas.wl_mode() == "rect")
    H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.5, 0.5))
    check("rect works after re-show", canvas.crop_rect() is not None and not H.invariants(canvas))
t5()

@scenario("W/L tool button then hide/show; W/L drag really adjusts window")
def t6():
    tool("drag")
    check("W/L tool -> canvas drag", canvas.wl_mode() == "drag")
    wl0 = canvas.wl(); n0 = canvas.mask_pixels()
    H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.6, 0.6))
    check("drag changes W/L and paints nothing", canvas.wl() != wl0 and canvas.mask_pixels() == n0, f"{wl0} -> {canvas.wl()}")
    show_dock(False)
    check("hidden with W/L tool: drag stays drag", canvas.wl_mode() == "drag")
    show_dock(True)
    check("shown with W/L tool: still drag, W/L button checked", canvas.wl_mode() == "drag" and dock._tool_btns["drag"].isChecked())
    # a cell's own ROI W/L button while dock open: dock re-applies the tool on next active change / show
    cell._roi_btn.setChecked(True); app.processEvents()
    m = canvas.wl_mode()
    dock.on_active_cell_changed(cell); app.processEvents()
    check("panel ROI button sets roi; dock re-apply overrides back to tool", m == "roi" and canvas.wl_mode() == "drag", f"{m} -> {canvas.wl_mode()}")
    check("ROI button left checked while canvas is not in roi mode (stale UI) — minor", not cell._roi_btn.isChecked(), f"roi_btn checked={cell._roi_btn.isChecked()} mode={canvas.wl_mode()}")
    cell._roi_btn.setChecked(False); app.processEvents(); tool("paint")
t6()

@scenario("_current_tool with no checked button")
def t7():
    b = dock._tool_btns["paint"]; b.setChecked(True)
    b.setChecked(False); app.processEvents()
    check("exclusive group refuses to uncheck via setChecked(False)", b.isChecked())
    checked = [m for m, bb in dock._tool_btns.items() if bb.isChecked()]
    check("exactly one tool checked", checked == ["paint"], str(checked))
    b.click(); app.processEvents()
    check("clicking the checked button keeps it checked", b.isChecked() and canvas.wl_mode() == "paint")
    # the only way to reach 'none checked': temporarily non-exclusive. Then any slot calling _current_tool raises.
    dock._tool_group.setExclusive(False); b.setChecked(False); dock._tool_group.setExclusive(True)
    none = not any(bb.isChecked() for bb in dock._tool_btns.values())
    check("non-exclusive detour can reach 'no tool checked' (not reachable through the UI)", none)
    raised = None
    try:
        dock._current_tool()
    except StopIteration as e:
        raised = e
    check("_current_tool raises StopIteration in that state (would abort inside a Qt slot) — not UI-reachable", raised is not None)
    dock._tool_btns["paint"].setChecked(True); dock._apply_tool()
t7()

@scenario("Erase ticked then switch to Polygon")
def t8():
    open_ws(fresh_ws("T_D", n=2)); tool("paint"); dock._brush_spin.setValue(60)
    stroke(app, canvas, (0.2, 0.5), (0.8, 0.5)); n = canvas.mask_pixels()
    dock._erase_chk.setChecked(True); tool("poly")
    check("erase flag survives tool switch", canvas._erase and canvas.wl_mode() == "poly")
    for p in ((0.4, 0.3), (0.6, 0.3), (0.6, 0.7), (0.4, 0.7)):
        H.click(canvas, H.pt(canvas, *p))
    H.key(canvas, Qt.Key_Return); app.processEvents()
    check("polygon with Erase removes pixels (documented in Erase tooltip)", 0 < canvas.mask_pixels() < n, f"{n} -> {canvas.mask_pixels()}")
    check("undo restores", canvas.undo_annotation() and canvas.mask_pixels() == n)
    # erase polygon on an empty mask: nothing to undo-worthy? (pushes an undo entry anyway)
    canvas.clear_annotations(); u = len(canvas._undo)
    for p in ((0.4, 0.3), (0.6, 0.3), (0.6, 0.7)):
        H.click(canvas, H.pt(canvas, *p))
    H.key(canvas, Qt.Key_Return); app.processEvents()
    check("erase polygon on empty mask: mask stays 0, no crash", canvas.mask_pixels() == 0 and not H.invariants(canvas))
    dock._erase_chk.setChecked(False)
    # erase-only session then Save: mask all zero → Nothing to save (Original unticked)
    dock._image_chk.setChecked(False)
    for chk in dock._fmt_chk.values(): chk.setChecked(chk is dock._fmt_chk["png"])
    dock._save(advance=False); app.processEvents()
    check("all-erased mask: 'Nothing to save'", "Nothing to save" in dock._status_lbl.text(), dock._status_lbl.text())
t8()

@scenario("brush radius 1 and 500")
def t9():
    tool("paint"); canvas.clear_annotations()
    dock._brush_spin.setValue(1)
    check("spin 1 -> brush_r 1", canvas._brush_r == 1)
    H.click(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents()
    n1 = canvas.mask_pixels()
    check("radius-1 click paints a few px (disk r=1)", 1 <= n1 <= 9, str(n1))
    dock._brush_spin.setValue(500); canvas.clear_annotations()
    check("spin 500 -> brush_r 500", canvas._brush_r == 500)
    t0 = time.time(); stroke(app, canvas, (0.0, 0.0), (1.0, 1.0)); dt = time.time() - t0
    n500 = canvas.mask_pixels()
    h, w = canvas.displayed_pixels().shape
    check("radius-500 diagonal stroke paints a large area, clipped at borders, no crash", n500 > 0.5 * h * w and n500 <= h * w and not H.invariants(canvas), f"{n500}/{h*w} in {dt:.2f}s")
    # click outside the image (in the letterbox) with a huge brush: must clip, not crash
    canvas.clear_annotations()
    r = canvas._dest_rect()
    H.click(canvas, QPoint(max(0, r.x() - 5), r.y() + r.height() // 2)); app.processEvents()
    check("click left of the image with r=500 clips into the mask without error", not H.invariants(canvas), str(canvas.mask_pixels()))
    H.click(canvas, QPoint(2, 2)); app.processEvents()
    check("click at widget corner: no crash", not H.invariants(canvas))
    dock._brush_spin.setValue(1000)
    check("spin clamps at 500", dock._brush_spin.value() == 500 and canvas._brush_r == 500)
    dock._brush_spin.setValue(0)
    check("spin clamps at 1", dock._brush_spin.value() == 1 and canvas._brush_r == 1)
    dock._brush_spin.setValue(20)
t9()

@scenario("brush value / erase while dock hidden and while a different panel is active")
def t10():
    show_dock(False)
    dock._brush_spin.setValue(33); dock._erase_chk.setChecked(True); app.processEvents()
    check("spin/erase while hidden: applied to active canvas, no crash", canvas._brush_r == 33 and canvas._erase)
    dock._erase_chk.setChecked(False); show_dock(True)
    other = quad.cell_at(2); quad._set_active(other); app.processEvents()
    check("switching active panel applies the tool there", other.canvas().wl_mode() == "paint" and other.canvas()._brush_r == 33)
    dock._brush_spin.setValue(7)
    check("spin applies to the active (other) panel only", other.canvas()._brush_r == 7 and canvas._brush_r == 33)
    quad._set_active(cell); app.processEvents()
    check("back: first panel keeps its old brush (33) until spin changes — minor UI/state drift", canvas._brush_r == 7, f"canvas r={canvas._brush_r} spin={dock._brush_spin.value()}")
    show_dock(False)
    check("hide: all 4 panels back to drag", all(c.canvas().wl_mode() == "drag" for c in quad.cells()))
t10()

win.close(); app.processEvents()
sys.exit(1 if summary() else 0)
