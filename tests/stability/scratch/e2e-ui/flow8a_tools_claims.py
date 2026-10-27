"""Flow 8a: README claims — Ctrl+Shift+W, tooltips, list double-click, Prev/Next, Brush radius,
Erase, Polygon Enter/Esc/right-click/double-click, Rect replace, W/L, Undo (Ctrl+Z) / Clear."""
import os, sys, shutil
import e2e_common as C
from e2e_common import check, H
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest

ROOT = os.path.join(C.FX, "ws_claims")
shutil.rmtree(os.path.join(ROOT, "vidi_output"), ignore_errors=True)
app, win = H.boot()
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()

# ── Ctrl+Shift+W toggles the dock ──
check("dock hidden initially", not dock.isVisible())
C.key_on(app, win, Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier)
check("Ctrl+Shift+W shows dock, button checked, active canvas → paint", dock.isVisible() and win._ws_btn.isChecked() and canvas.wl_mode() == "paint", canvas.wl_mode())
C.key_on(app, win, Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier)
check("Ctrl+Shift+W hides dock, all panels back to drag", not dock.isVisible() and not win._ws_btn.isChecked() and all(c.canvas().wl_mode() == "drag" for c in quad.cells()))
C.key_on(app, win, Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier)
check("shown again", dock.isVisible())

# ── tooltips mention the documented shortcuts / behaviours ──
tt = lambda w: w.toolTip()
check("Workspace button tooltip mentions Ctrl+Shift+W", "Ctrl+Shift+W" in tt(win._ws_btn), tt(win._ws_btn))
check("Save & Next tooltip mentions Ctrl+S", "Ctrl+S" in tt(dock._save_next_btn), tt(dock._save_next_btn))
check("Undo tooltip mentions Ctrl+Z", "Ctrl+Z" in tt(dock._undo_btn), tt(dock._undo_btn))
pt_ = tt(dock._tool_btns["poly"])
check("Polygon tooltip: double-click/Enter, right-click, Esc", all(s in pt_ for s in ("double-click or Enter", "right-click", "Esc")), pt_)
check("Rect tooltip: crop rectangle", "crop rectangle" in tt(dock._tool_btns["rect"]), tt(dock._tool_btns["rect"]))
check("Brush spin tooltip: image pixels", "image pixels" in tt(dock._brush_spin), tt(dock._brush_spin))
check("list tooltip: double-click loads", "Double-click" in tt(dock._list), tt(dock._list))
check("Save button has no tooltip (observe)", tt(dock._save_btn) == "", tt(dock._save_btn))
check("Clear tooltip: mask + rectangle", "mask" in tt(dock._clear_btn) and "rectangle" in tt(dock._clear_btn), tt(dock._clear_btn))

# ── open, list double-click, Prev/Next ──
C.open_dir_via_ui(app, win, ROOT)
ws = dock.workspace()
check("3 items, first loaded", ws is not None and len(ws.items) == 3 and H.wait_loaded(app, cell))
C.dclick_list_row(app, dock, 2)
check("double-click row 3 in the list loads item 3", H.wait_loaded(app, cell) and dock._index == 2 and os.path.abspath(cell.series_data().meta.series_dir) == ws.items[2].path and dock._list.currentRow() == 2, str(dock._index))
check("Next disabled on last, Prev enabled", not dock._next_btn.isEnabled() and dock._prev_btn.isEnabled())
C.click_button(app, dock._prev_btn)
check("Prev → item 2", H.wait_loaded(app, cell) and dock._index == 1 and os.path.abspath(cell.series_data().meta.series_dir) == ws.items[1].path)
C.click_button(app, dock._prev_btn)
check("Prev → item 1, Prev disabled", H.wait_loaded(app, cell) and dock._index == 0 and not dock._prev_btn.isEnabled())

# ── Brush: radius in image px (exact disk), spin edit, Erase ──
def disk_count(rad):
    yy, xx = np.ogrid[-rad:rad + 1, -rad:rad + 1]
    return int(((xx * xx + yy * yy) <= rad * rad).sum())
check("default brush 20 px", dock._brush_spin.value() == 20)
H.click(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents()
check("single click paints exactly one r=20 disk", canvas.mask_pixels() == disk_count(20), f"{canvas.mask_pixels()} vs {disk_count(20)}")
dock._brush_spin.selectAll(); QTest.keyClicks(dock._brush_spin, "5"); app.processEvents()
check("typed brush 5", dock._brush_spin.value() == 5, str(dock._brush_spin.value()))
H.click(canvas, H.pt(canvas, 0.2, 0.2)); app.processEvents()
check("second click adds exactly one r=5 disk", canvas.mask_pixels() == disk_count(20) + disk_count(5), str(canvas.mask_pixels()))
check("stats label updated", f"mask {disk_count(20) + disk_count(5):,} px" in dock._stats_lbl.text(), dock._stats_lbl.text())
C.click_button(app, dock._erase_chk)
check("Erase ticked via click", dock._erase_chk.isChecked())
H.click(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents()
check("erase click removes r=5 disk from the r=20 disk", canvas.mask_pixels() == disk_count(20) + disk_count(5) - disk_count(5), str(canvas.mask_pixels()))
C.click_button(app, dock._erase_chk)
check("Erase unticked", not dock._erase_chk.isChecked())

# ── Undo via Ctrl+Z (window shortcut, focus on canvas) and the button ──
n_before = canvas.mask_pixels()
C.key_on(app, canvas, Qt.Key_Z, Qt.ControlModifier)
check("Ctrl+Z undoes the erase", canvas.mask_pixels() == disk_count(20) + disk_count(5), str(canvas.mask_pixels()))
C.click_button(app, dock._undo_btn)
check("Undo button undoes the r=5 click", canvas.mask_pixels() == disk_count(20), str(canvas.mask_pixels()))
C.click_button(app, dock._undo_btn)
check("Undo again → empty", canvas.mask_pixels() == 0)
C.click_button(app, dock._undo_btn)
check("Undo on empty stack → 'Nothing to undo.' status", dock._status_lbl.text() == "Nothing to undo.", dock._status_lbl.text())

# undo depth: 12 clicks, then 12 undos
dock._brush_spin.selectAll(); QTest.keyClicks(dock._brush_spin, "3"); app.processEvents()
for i in range(12):
    H.click(canvas, H.pt(canvas, 0.1 + 0.06 * i, 0.9)); app.processEvents()
check("12 separate r=3 disks", canvas.mask_pixels() == 12 * disk_count(3), str(canvas.mask_pixels()))
ok = [canvas.undo_annotation() for _ in range(10)]
check("10 undos succeed, 2 disks remain (undo depth 10)", all(ok) and canvas.mask_pixels() == 2 * disk_count(3), str(canvas.mask_pixels()))
check("11th undo returns False", not canvas.undo_annotation())

# ── Polygon: Enter fills (focus from a click), Esc cancels, right-click drops vertex, erase ──
C.click_button(app, dock._clear_btn)
check("Clear empties the mask", canvas.mask_pixels() == 0)
C.click_button(app, dock._tool_btns["poly"])
C.click_focus(canvas, H.pt(canvas, 0.2, 0.2))
for p in (H.pt(canvas, 0.5, 0.2), H.pt(canvas, 0.5, 0.5)):
    H.click(canvas, p)
app.processEvents()
check("canvas has keyboard focus after clicking on it", app.focusWidget() is canvas, str(app.focusWidget()))
QTest.keyClick(app.focusWidget(), Qt.Key_Return); app.processEvents()
n_tri = canvas.mask_pixels()
Hh, Ww = canvas.displayed_pixels().shape
check("Enter fills the triangle (≈ half of 0.3W×0.3H)", abs(n_tri - 0.5 * 0.3 * Ww * 0.3 * Hh) < 0.1 * 0.3 * Ww * 0.3 * Hh, f"{n_tri} vs {0.5 * 0.3 * Ww * 0.3 * Hh:.0f}")
C.poly(canvas, (H.pt(canvas, 0.6, 0.6), H.pt(canvas, 0.9, 0.6), H.pt(canvas, 0.9, 0.9)))
QTest.keyClick(app.focusWidget(), Qt.Key_Escape); app.processEvents()
check("Esc cancels: no vertices, mask unchanged", len(canvas._poly_pts) == 0 and canvas.mask_pixels() == n_tri)
C.poly(canvas, (H.pt(canvas, 0.6, 0.6), H.pt(canvas, 0.9, 0.6), H.pt(canvas, 0.9, 0.9), H.pt(canvas, 0.6, 0.9)))
H.click(canvas, H.pt(canvas, 0.75, 0.75), Qt.RightButton); app.processEvents()
check("right-click drops the last vertex (4 → 3)", len(canvas._poly_pts) == 3, str(canvas._poly_pts))
H.dclick(canvas, H.pt(canvas, 0.9, 0.9)); app.processEvents()
n_two = canvas.mask_pixels()
check("double-click fills the remaining triangle", n_two > n_tri and not quad.is_fullscreen(), f"{n_two}")
# erase polygon over everything
C.click_button(app, dock._erase_chk)
C.poly(canvas, (H.pt(canvas, 0.0, 0.0), H.pt(canvas, 1.0, 0.0), H.pt(canvas, 1.0, 1.0), H.pt(canvas, 0.0, 1.0)))
check("focus back on canvas after clicking it (Erase checkbox had focus)", app.focusWidget() is canvas, str(app.focusWidget()))
QTest.keyClick(app.focusWidget(), Qt.Key_Return); app.processEvents()
check("Erase + polygon removes (mask → 0)", canvas.mask_pixels() == 0, str(canvas.mask_pixels()))
C.click_button(app, dock._erase_chk)
C.key_on(app, canvas, Qt.Key_Z, Qt.ControlModifier)
check("Ctrl+Z restores both triangles", canvas.mask_pixels() == n_two)
# Enter with < 3 vertices does nothing
C.poly(canvas, (H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.4, 0.3)))
QTest.keyClick(app.focusWidget(), Qt.Key_Return); app.processEvents()
check("Enter with 2 vertices: no fill, vertices dropped", canvas.mask_pixels() == n_two and len(canvas._poly_pts) == 0)

# ── Rect: drag, drag again replaces, tiny click keeps; W/L back to drag ──
C.click_button(app, dock._tool_btns["rect"])
H.drag(app, canvas, H.pt(canvas, 0.1, 0.1), H.pt(canvas, 0.4, 0.4)); r1 = canvas.crop_rect()
H.drag(app, canvas, H.pt(canvas, 0.5, 0.5), H.pt(canvas, 0.9, 0.9)); r2 = canvas.crop_rect()
check("second drag replaces the rectangle", r1 is not None and r2 is not None and r2 != r1 and r2[0] > r1[2], f"{r1} → {r2}")
H.click(canvas, H.pt(canvas, 0.3, 0.3)); app.processEvents()
check("a click in Rect mode keeps the previous rectangle", canvas.crop_rect() == r2)
H.drag(app, canvas, H.pt(canvas, 0.5, 0.5), H.pt(canvas, 1.3, 1.3)); r3 = canvas.crop_rect()
check("drag past the image edge clamps to bounds", r3 is not None and r3[2] == Ww and r3[3] == Hh, f"{r3} vs {Ww}x{Hh}")
check("invariants ok", not H.invariants(canvas), str(H.invariants(canvas)))
C.click_button(app, dock._tool_btns["drag"])
check("W/L button → drag mode", canvas.wl_mode() == "drag")
wl0 = canvas.wl(); n0 = canvas.mask_pixels()
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.6, 0.6))
check("W/L drag changes window, not mask/rect", canvas.wl() != wl0 and canvas.mask_pixels() == n0 and canvas.crop_rect() == r3, f"{wl0} → {canvas.wl()}")

# ── Clear wipes mask + rectangle; Undo after Clear ──
C.click_button(app, dock._clear_btn)
check("Clear: mask 0, rect None, stats label", canvas.mask_pixels() == 0 and canvas.crop_rect() is None and dock._stats_lbl.text() == "mask 0 px · no rectangle", dock._stats_lbl.text())
C.key_on(app, canvas, Qt.Key_Z, Qt.ControlModifier)
check("Ctrl+Z after Clear restores the mask", canvas.mask_pixels() == n0, str(canvas.mask_pixels()))
check("README: undo 'steps back through clears' — rectangle restored too?", canvas.crop_rect() == r3, f"rect after undo = {canvas.crop_rect()} (was {r3})")

# ── Ctrl+Z / Undo while dock hidden: no-op ──
C.key_on(app, win, Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier)
check("dock hidden", not dock.isVisible())
C.key_on(app, canvas, Qt.Key_Z, Qt.ControlModifier)
check("Ctrl+Z with dock hidden is a no-op", canvas.mask_pixels() == n0)
sys.exit(C.finish(win, app))
