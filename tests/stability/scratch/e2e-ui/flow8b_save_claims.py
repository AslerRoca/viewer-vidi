"""Flow 8b: README claims around saving — custom output dir, 'sub/out', invert + W/L 'what you see',
hidden-dock Ctrl+S, multi-panel mismatch via clicks, .lst / headerless CSV lists, 3-D DICOM per-file items,
fast double Ctrl+S."""
import os, sys, shutil, time
import e2e_common as C
from e2e_common import check, H
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PIL import Image
import nibabel as nib

ROOT = os.path.join(C.FX, "ws_outdir")
for d in ("vidi_output", "my_out", "sub"):
    shutil.rmtree(os.path.join(ROOT, d), ignore_errors=True)
app, win = H.boot()
dock, quad = win._dock, win._quad
C.click_button(app, win._ws_btn)
cell = quad.active_cell(); canvas = cell.canvas()
from viewer_vidi.annotation_export import window_to_uint8
from viewer_vidi import workspace as W

C.open_dir_via_ui(app, win, ROOT)
ws = dock.workspace()
check("2 items loaded", ws is not None and len(ws.items) == 2 and H.wait_loaded(app, cell))
stem = ws.items[0].stem

# ── custom output dir typed into the field ──
dock._out_edit.selectAll(); QTest.keyClicks(dock._out_edit, "my_out"); app.processEvents()
check("typed output dir", dock._out_edit.text() == "my_out")
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.5, 0.3))
C.click_button(app, dock._save_btn); st = C.wait_status(app, dock)
check("status names my_out/", st == "Saved 1 file(s) → my_out/ (png)", st)
check("file under <root>/my_out/png", os.path.isfile(os.path.join(ROOT, "my_out", "png", f"{stem}_mask.png")) and os.path.isfile(os.path.join(ROOT, "my_out", "manifest.csv")))
check("nothing under vidi_output", not os.path.exists(os.path.join(ROOT, "vidi_output")))

# ── invert + explicit W/L: PNG == window_to_uint8 and vs what is on screen ──
C.click_button(app, win._invert_btn)
check("toolbar Invert → canvas.invert()", canvas.invert() is True)
win._wc_spin.setValue(1500.0); win._ww_spin.setValue(900.0); app.processEvents()
wc, ww = canvas.wl()
check("W/L spin boxes applied to the canvas", (wc, ww) == (1500.0, 900.0), f"{wc} {ww}")
C.click_button(app, dock._image_chk)
C.click_button(app, dock._save_btn); st = C.wait_status(app, dock)
check("saved image+mask", st == "Saved 2 file(s) → my_out/ (png)", st)
px = canvas.displayed_pixels()
pimg = np.array(Image.open(os.path.join(ROOT, "my_out", "png", f"{stem}_image.png")))
check("png image == window_to_uint8(px, 1500, 900, invert=True)", np.array_equal(pimg, window_to_uint8(px, wc, ww, True)))
screen = canvas._rgb_buf
if screen is not None and screen.shape[:2] == px.shape:
    d = np.abs(pimg.astype(np.int16) - screen[..., 0].astype(np.int16))
    check("README 'what you see': PNG equals on-screen grey exactly", d.max() == 0, f"max diff {d.max()}, differing px {(d > 0).sum()} of {d.size} ({(d > 0).mean():.1%})")
else:
    check("screen buffer available", False, str(None if screen is None else screen.shape))
C.click_button(app, win._invert_btn)   # invert off again

# ── 'sub/out' output dir → files nest; reopen rescans exported PNGs as items? ──
dock._out_edit.selectAll(); QTest.keyClicks(dock._out_edit, "sub/out"); app.processEvents()
C.click_button(app, dock._next_btn); H.wait_loaded(app, cell)
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.5, 0.3))
C.click_button(app, dock._save_btn); st = C.wait_status(app, dock)
check("'sub/out' accepted: files under <root>/sub/out/png", st.startswith("Saved 2 file(s) → sub/out/") and os.path.isfile(os.path.join(ROOT, "sub", "out", "png", f"{ws.items[1].stem}_image.png")), st)
C.open_dir_via_ui(app, win, ROOT)
ws2 = dock.workspace()
check("reopen with 'sub/out': exported PNGs are NOT rescanned as items", ws2 is not None and len(ws2.items) == 2, str(ws2 and [os.path.relpath(it.path, ROOT) for it in ws2.items]))
check("reopen with 'sub/out': ✓ restored from sub/out/manifest.csv", ws2 is not None and ws2.items[1].done and dock._index == 0, str(ws2 and [it.done for it in ws2.items]))
dock._out_edit.selectAll(); QTest.keyClicks(dock._out_edit, "vidi_output"); app.processEvents()

# ── multi-panel: click on cell 2 (empty) → Ctrl+S status; Next loads into cell 2; click cell 1 → mismatch box ──
C.open_dir_via_ui(app, win, ROOT); ws = dock.workspace(); H.wait_loaded(app, cell)
cell2 = quad.cells()[1]
QTest.mouseClick(cell2, Qt.LeftButton); app.processEvents()
check("click on panel 2 makes it active; its canvas takes the tool", quad.active_cell() is cell2 and cell2.canvas().wl_mode() == dock._current_tool(), f"{quad.active_cell()} {cell2.canvas().wl_mode()}")
C.ctrl_s(app, win, target=cell2); st = C.wait_status(app, dock)
check("Ctrl+S with an EMPTY active panel: status text (observe)", st == "Image still loading — try again in a moment.", st)
C.click_button(app, dock._next_btn)
check("Next loads item 2 into the active panel 2", H.wait_loaded(app, cell2) and os.path.abspath(cell2.series_data().meta.series_dir) == ws.items[1].path and dock._index == 1)
check("panel 1 still shows item 1", os.path.abspath(cell.series_data().meta.series_dir) == ws.items[0].path)
H.click(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents()     # click on panel 1's canvas → active
check("panel 1 active again (mask painted there since tool=paint)", quad.active_cell() is cell and canvas.wl_mode() == "paint")
seen = C.arm_dialog_closer(app)
C.ctrl_s(app, win, target=canvas); app.processEvents(); H.pump(app, 400)
check("Ctrl+S → 'Panel mismatch' warning, item 2 not done", len(seen) == 1 and seen[0][1] == "Panel mismatch" and not ws.items[1].done, str(seen))
check("mismatch box text names both paths", seen and ws.items[0].path in seen[0][2] and ws.items[1].path in seen[0][2], str(seen and seen[0][2]))
C.dclick_list_row(app, dock, 1)
check("double-click item 2 → loads into panel 1 (active)", H.wait_loaded(app, cell) and os.path.abspath(cell.series_data().meta.series_dir) == ws.items[1].path, f"active={quad.cells().index(quad.active_cell())} index={dock._index} shows={cell.series_data() and os.path.basename(cell.series_data().meta.series_dir)}")
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.5, 0.3))
C.ctrl_s(app, win, target=canvas); st = C.wait_status(app, dock)
check("then Ctrl+S saves", st.startswith("Saved"), f"{st} active={quad.cells().index(quad.active_cell())} sd={cell.series_data() is not None} px={canvas.displayed_pixels() is not None}")

# ── hidden dock + Ctrl+S ──
HID = os.path.join(C.FX, "ws_hidden"); shutil.rmtree(os.path.join(HID, "vidi_output"), ignore_errors=True)
C.open_dir_via_ui(app, win, HID); wsh = dock.workspace(); H.wait_loaded(app, cell)
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.5, 0.3)); nh = canvas.mask_pixels()
C.key_on(app, win, Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier)
check("dock hidden, canvas back to drag, mask kept", not dock.isVisible() and canvas.wl_mode() == "drag" and canvas.mask_pixels() == nh)
C.ctrl_s(app, win, target=canvas); H.pump(app, 300)
saved_hidden = os.path.isfile(os.path.join(HID, "vidi_output", "png", f"{wsh.items[0].stem}_mask.png"))
check("Ctrl+S with the dock HIDDEN does nothing (FAIL = it saved/advanced while hidden)", not saved_hidden and not wsh.items[0].done and dock._index == 0, f"saved={saved_hidden} done={wsh.items[0].done} index={dock._index} status={dock._status_lbl.text()!r}")
H.wait_loaded(app, cell)
check("hidden Ctrl+S left the active panel on item 1 (FAIL = image swapped while dock hidden)", os.path.abspath(cell.series_data().meta.series_dir) == wsh.items[0].path, os.path.basename(cell.series_data().meta.series_dir))
check("dock still hidden → canvas must be in drag mode (FAIL = paint mode leaked while hidden)", canvas.wl_mode() == "drag", canvas.wl_mode())
C.key_on(app, win, Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier)

# ── .lst list (relative, comments) and headerless CSV via Open list… ──
LST = os.path.join(C.FX, "ws_lst")
shutil.rmtree(os.path.join(LST, "vidi_output"), ignore_errors=True)
seen = C.open_list_via_ui(app, win, os.path.join(LST, "cohort.lst"))
wsl = dock.workspace()
check(".lst: 2 items, '../' relative resolved, comment skipped, root = list dir", seen == [] and wsl is not None and [it.stem for it in wsl.items] == ["bpd1_20100102_1", "bpd1_20100107_1"] and wsl.root == LST, str(wsl and ([it.stem for it in wsl.items], wsl.root)))
check("label: LIST mode · list cohort.lst · 2 items", "LIST mode · list cohort.lst · 2 items" in dock._ws_lbl.text(), dock._ws_lbl.text())
check("tooltip = root when nothing missing", dock._ws_lbl.toolTip() == LST, dock._ws_lbl.toolTip())
seen = C.open_list_via_ui(app, win, os.path.join(LST, "noheader.csv"))
wsc = dock.workspace()
check("headerless CSV: first column used, 2 items in file order", wsc is not None and [it.stem for it in wsc.items] == ["bpd1_20100115_1", "bpd1_20100102_1"], str(wsc and [it.stem for it in wsc.items]))
check("list item loads", H.wait_loaded(app, cell))

# ── 3-D DICOM series dir: each file one item ──
MR = os.path.join(C.FX, "ws_mr"); shutil.rmtree(os.path.join(MR, "vidi_output"), ignore_errors=True)
C.open_dir_via_ui(app, win, MR); wsm = dock.workspace()
check("20 extensionless DICOM files → 20 items with bare stems", wsm is not None and len(wsm.items) == 20 and wsm.items[0].stem == os.path.basename(wsm.items[0].path), str(wsm and [it.stem for it in wsm.items][:3]))
check("item 1 (single slice) loads", H.wait_loaded(app, cell), str(cell.series_data() and cell.series_data().meta.series_dir))
px = canvas.displayed_pixels()
check("single-file item is 2-D with the mask allocated", px.ndim == 2 and canvas.mask() is not None and canvas.mask().shape == px.shape, f"{px.shape}")
C.click_button(app, dock._fmt_chk["nifti"])
H.drag(app, canvas, H.pt(canvas, 0.4, 0.4), H.pt(canvas, 0.6, 0.6))
sp = cell.series_data().pixel_spacing
C.ctrl_s(app, win, target=canvas); st = C.wait_status(app, dock)
check("MR slice saved png+nifti (image ticked)", st == "Saved 4 file(s) → vidi_output/ (png, nifti)", f"{st} image={dock._image_chk.isChecked()} fmts={[k for k,v in dock._fmt_chk.items() if v.isChecked()]} active={quad.cells().index(quad.active_cell())}")
if not st.startswith("Saved 4"):
    sys.exit(C.finish(win, app))
ni = nib.load(os.path.join(MR, "vidi_output", "nifti", f"{wsm.items[0].stem}_image.nii.gz"))
check("MR nifti == displayed slice", np.array_equal(np.asarray(ni.dataobj), px.T[..., None]), str(ni.shape))
check("MR nifti zooms = pixel spacing (col,row)", np.allclose(ni.header.get_zooms()[:2], (sp[1], sp[0])), f"{ni.header.get_zooms()[:2]} vs {sp}")
# fast double Ctrl+S: Save & Next then Ctrl+S again before the next item has loaded
H.wait_loaded(app, cell)
H.drag(app, canvas, H.pt(canvas, 0.4, 0.4), H.pt(canvas, 0.6, 0.6))
seen = C.arm_dialog_closer(app)
C.ctrl_s(app, win, target=canvas)           # saves item 2, starts loading item 3
st1 = dock._status_lbl.text()
C.ctrl_s(app, win, target=canvas)           # immediately again
st2 = dock._status_lbl.text(); H.pump(app, 500)
check("fast double Ctrl+S: 2nd press gives 'still loading' status, no dialog", st1.startswith("Saved") and st2 == "Image still loading — try again in a moment." and seen == [], f"st1={st1!r} st2={st2!r} seen={seen}")
H.wait_loaded(app, cell)
check("after load: index 2, item 3 shown, items 1-2 done, item 3 pending", dock._index == 2 and wsm.items[0].done and wsm.items[1].done and not wsm.items[2].done and os.path.abspath(cell.series_data().meta.series_dir) == wsm.items[2].path, f"{dock._index}")
check("invariants ok", not H.invariants(canvas), str(H.invariants(canvas)))
sys.exit(C.finish(win, app))
