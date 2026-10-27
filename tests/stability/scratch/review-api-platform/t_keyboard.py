"""Keyboard focus interactions: Ctrl+Z in the Output-dir QLineEdit / brush QSpinBox / list / canvas,
Ctrl+S while a modal dialog is up, Ctrl+S with the dock hidden, Esc/Enter in polygon mode."""
import os, sys, shutil
from common import *
import harness as H
import numpy as np
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QMessageBox
app, win = H.boot()
D = os.path.join(SCR, "data", "ws_kb"); shutil.rmtree(D, ignore_errors=True); os.makedirs(D)
for f in sorted(os.listdir(FIX))[:3]: shutil.copy(os.path.join(FIX, f), D)
ws = H.open_workspace(app, win, D)
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
check("workspace open, paint tool", canvas.wl_mode() == "paint" and len(ws.items) == 3)
H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.5, 0.2)); n1 = canvas.mask_pixels()
H.drag(app, canvas, H.pt(canvas, 0.2, 0.4), H.pt(canvas, 0.5, 0.4)); n2 = canvas.mask_pixels()
check("two strokes", 0 < n1 < n2, f"{n1} {n2}")

# ── Ctrl+Z inside the Output dir line edit ──────────────────────────────────
le = dock._out_edit
le.setFocus(); app.processEvents()
check("line edit has focus", app.focusWidget() is le)
QTest.keyClicks(le, "xyz"); app.processEvents()
check("typed into line edit", le.text() == "vidi_outputxyz", le.text())
QTest.keyClick(le, Qt.Key_Z, Qt.ControlModifier); app.processEvents()
print(f"after Ctrl+Z in line edit: text={le.text()!r} mask={canvas.mask_pixels()} (before {n2})")
check("Ctrl+Z in line edit = TEXT undo (text reverted)", le.text() != "vidi_outputxyz", le.text())
check("Ctrl+Z in line edit did NOT undo the mask", canvas.mask_pixels() == n2, f"{canvas.mask_pixels()} vs {n2}")
le.setText("vidi_output")

# ── Ctrl+Z inside the brush spin box ────────────────────────────────────────
sp = dock._brush_spin; sp.setFocus(); app.processEvents(); sp.selectAll()
QTest.keyClicks(sp, "7"); app.processEvents()
v_typed = sp.value(); n_before = canvas.mask_pixels()
QTest.keyClick(sp, Qt.Key_Z, Qt.ControlModifier); app.processEvents()
print(f"after Ctrl+Z in spin: value={sp.value()} (typed {v_typed}) mask={canvas.mask_pixels()}")
check("Ctrl+Z in spin box did NOT undo the mask", canvas.mask_pixels() == n_before)
sp.setValue(20)

# ── Ctrl+Z with the item list focused → mask undo ───────────────────────────
dock._list.setFocus(); app.processEvents()
QTest.keyClick(dock._list, Qt.Key_Z, Qt.ControlModifier); app.processEvents()
check("Ctrl+Z with list focused undoes the mask", canvas.mask_pixels() == n1, f"{canvas.mask_pixels()} vs {n1}")
# ── Ctrl+Z with the canvas focused → mask undo ──────────────────────────────
canvas.setFocus(); app.processEvents()
QTest.keyClick(canvas, Qt.Key_Z, Qt.ControlModifier); app.processEvents()
check("Ctrl+Z with canvas focused undoes the mask", canvas.mask_pixels() == 0, str(canvas.mask_pixels()))
# ── Esc / Enter in polygon mode ─────────────────────────────────────────────
dock._tool_btns["poly"].setChecked(True); dock._apply_tool()
for p in (H.pt(canvas, 0.3, 0.5), H.pt(canvas, 0.6, 0.5), H.pt(canvas, 0.6, 0.8)): H.click(canvas, p)
check("3 vertices pending", len(canvas._poly_pts) == 3)
check("canvas took focus from the clicks (ClickFocus)", app.focusWidget() is canvas, str(app.focusWidget()))
QTest.keyClick(canvas, Qt.Key_Escape); app.processEvents()
check("Esc cancels the polygon", canvas._poly_pts == [] and canvas.mask_pixels() == 0)
for p in (H.pt(canvas, 0.3, 0.5), H.pt(canvas, 0.6, 0.5), H.pt(canvas, 0.6, 0.8)): H.click(canvas, p)
dock._list.setFocus(); app.processEvents()
QTest.keyClick(dock._list, Qt.Key_Return); app.processEvents()
print("Enter with list focused: pending vertices", len(canvas._poly_pts), "mask", canvas.mask_pixels())
canvas.setFocus(); QTest.keyClick(canvas, Qt.Key_Return); app.processEvents()
n_poly = canvas.mask_pixels()
check("Enter with canvas focused fills the polygon", n_poly > 0 and canvas._poly_pts == [], str(n_poly))

# ── Ctrl+S while a modal dialog is open ─────────────────────────────────────
saves = []
orig_save = dock._save
dock._save = lambda advance: saves.append(advance)
box = QMessageBox(win); box.setWindowTitle("probe"); box.setText("modal"); box.setWindowModality(Qt.ApplicationModal)
box.show(); box.activateWindow(); app.processEvents()
print("activeWindow is box:", app.activeWindow() is box, "activeModalWidget:", app.activeModalWidget())
QTest.keyClick(box, Qt.Key_S, Qt.ControlModifier); app.processEvents()
check("Ctrl+S while modal QMessageBox is active does not save", saves == [], str(saves))
box.close(); app.processEvents(); win.activateWindow(); app.processEvents()
QTest.keyClick(win, Qt.Key_S, Qt.ControlModifier); app.processEvents()
check("Ctrl+S on the main window reaches save_and_next", saves == [True], str(saves))
dock._save = orig_save; saves.clear()

# ── Ctrl+S with the dock hidden ─────────────────────────────────────────────
win._ws_btn.setChecked(False); app.processEvents()
check("dock hidden → canvas back to drag", not dock.isVisible() and canvas.wl_mode() == "drag")
idx0 = dock._index
QTest.keyClick(win, Qt.Key_S, Qt.ControlModifier); app.processEvents()
H.wait_loaded(app, cell)
outd = os.path.join(D, "vidi_output", "png")
files = sorted(os.listdir(outd)) if os.path.isdir(outd) else []
print(f"Ctrl+S with dock hidden: files={files} index {idx0}->{dock._index} mode={canvas.wl_mode()} done={[it.done for it in ws.items]}")
check("Ctrl+S with the dock hidden does not write files / advance", files == [] and dock._index == idx0, f"files={files} idx={dock._index}")
check("after Ctrl+S with dock hidden every panel is still in drag mode", all(c.canvas().wl_mode() == "drag" for c in quad.cells()),
      str([c.canvas().wl_mode() for c in quad.cells()]))
win._ws_btn.setChecked(True); app.processEvents()
win.close(); app.processEvents()
sys.exit(summary())
