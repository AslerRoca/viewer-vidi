"""Flow 2: list mode via CSV 'id,path,label' with relative paths and one missing → Open list…"""
import os, sys, shutil
import e2e_common as C
from e2e_common import check, H

ROOT = os.path.join(C.FX, "ws_csv")
LIST = os.path.join(ROOT, "cohort.csv")
shutil.rmtree(os.path.join(ROOT, "vidi_output"), ignore_errors=True)

app, win = H.boot()
dock, quad = win._dock, win._quad
C.click_button(app, win._ws_btn)
cell = quad.active_cell(); canvas = cell.canvas()

seen = C.open_list_via_ui(app, win, LIST)
check("no dialog for a usable list", seen == [], str(seen))
ws = dock.workspace()
check("list mode workspace, root = list dir", ws is not None and ws.mode == "list" and ws.root == ROOT and ws.list_file == LIST, str(ws and (ws.mode, ws.root)))
check("2 existing items, relative paths resolved", len(ws.items) == 2 and all(os.path.isabs(it.path) and it.path.startswith(ROOT + "/imgs/") for it in ws.items), str([it.path for it in ws.items]))
check("1 missing", ws.missing == [os.path.join(ROOT, "imgs", "does_not_exist.dcm")], str(ws.missing))
lbl = dock._ws_lbl.text()
check("status label: LIST mode · list cohort.csv · 2 items · 1 listed path(s) not found", "LIST mode" in lbl and "list cohort.csv" in lbl and "2 items" in lbl and "1 listed path(s) not found" in lbl, lbl)
tip = dock._ws_lbl.toolTip()
check("tooltip lists the missing path", tip == os.path.join(ROOT, "imgs", "does_not_exist.dcm"), tip)
check("first item loaded", H.wait_loaded(app, cell) and os.path.abspath(cell.series_data().meta.series_dir) == ws.items[0].path)
check("count 1/2 · 0 done", dock._count_lbl.text() == "1/2 · 0 done", dock._count_lbl.text())

# save one via the Save button (no advance)
H.drag(app, canvas, H.pt(canvas, 0.4, 0.4), H.pt(canvas, 0.5, 0.5))
C.click_button(app, dock._save_btn)
st = C.wait_status(app, dock)
check("Save (button) writes png mask only (default ticks: png, mask+crop, no rect)", st == "Saved 1 file(s) → vidi_output/ (png)", st)
check("Save does not advance", dock._index == 0 and ws.items[0].done and C.list_texts(dock)[0].startswith("✓ "), str(C.list_texts(dock)))
check("output inside list dir", os.path.isfile(os.path.join(ROOT, "vidi_output", "png", ws.items[0].stem + "_mask.png")))

# Open list… again (same list) → done flag restored, first pending = index 1
seen = C.open_list_via_ui(app, win, LIST)
ws2 = dock.workspace()
check("reopen list: ✓ restored and first pending (index 1) selected", ws2.items[0].done and not ws2.items[1].done and dock._index == 1 and C.list_texts(dock) == ["✓ " + ws2.items[0].stem, "○ " + ws2.items[1].stem], f"{dock._index} {C.list_texts(dock)}")
check("status cleared on reopen", dock._status_lbl.text() == "", dock._status_lbl.text())
check("item 2 loaded after reopen", H.wait_loaded(app, cell) and os.path.abspath(cell.series_data().meta.series_dir) == ws2.items[1].path)

# a list whose paths are all missing → 'Empty list' warning, workspace unchanged
bad = os.path.join(C.SCRATCH, "all_missing.txt")
open(bad, "w").write("/nonexistent/a.dcm\n/nonexistent/b.dcm\n")
seen = C.open_list_via_ui(app, win, bad)
check("all-missing list → 'Empty list' warning", len(seen) == 1 and seen[0][1] == "Empty list", str(seen))
check("workspace unchanged after warning", dock.workspace() is ws2)

# cancel in the file dialog → nothing happens
seen = C.open_list_via_ui(app, win, "")
check("cancel file dialog: no dialog, workspace unchanged", seen == [] and dock.workspace() is ws2)

# TSV with 'filename' header and quoted entries, absolute paths incl. a 3-D NIfTI and an RGBA PNG
tsv = os.path.join(C.SCRATCH, "mixed.tsv")
NII = "/media/zsk/ressd/research/alldata_backup/Tongyu_Wang/radiology_qingyi/qingyi/+C/2035104/C.nii"
PNG = "/media/zsk/ressd/research/alldata_backup/project_workstation/PhD/image_exsample/3.png"
open(tsv, "w").write(f"id\tfilename\tnote\n7\t\"{NII}\"\tnifti 3d\n8\t{PNG}\trgba png\n")
shutil.rmtree(os.path.join(C.SCRATCH, "vidi_output"), ignore_errors=True)
seen = C.open_list_via_ui(app, win, tsv)
ws3 = dock.workspace()
check("tsv: 2 items (C, 3), root = scratch dir", ws3 is not None and [it.stem for it in ws3.items] == ["C", "3"] and ws3.root == C.SCRATCH, str(ws3 and [it.stem for it in ws3.items]))
check("3-D NIfTI item loads", H.wait_loaded(app, cell), str(cell.series_data() and cell.series_data().meta.series_dir))
import numpy as np
px = canvas.displayed_pixels()
check("NIfTI displayed slice is 2-D float32 with mask", px.ndim == 2 and px.dtype == np.float32 and canvas.mask().shape == px.shape, f"{px.shape} {px.dtype}")
# scroll one slice with the wheel on the canvas, then annotate + save
from PyQt5.QtCore import Qt, QPoint, QEvent
from PyQt5.QtGui import QWheelEvent
from PyQt5.QtWidgets import QApplication
z0 = cell._cur_z
ev = QWheelEvent(QPoint(10, 10), canvas.mapToGlobal(QPoint(10, 10)), QPoint(0, 0), QPoint(0, -120), Qt.NoButton, Qt.NoModifier, Qt.ScrollUpdate, False)
QApplication.sendEvent(canvas, ev); app.processEvents()
check("wheel changed slice", cell._cur_z != z0, f"{z0} → {cell._cur_z}")
check("mask survives slice change with same shape", canvas.mask() is not None and canvas.mask().shape == canvas.displayed_pixels().shape)
H.drag(app, canvas, H.pt(canvas, 0.4, 0.4), H.pt(canvas, 0.5, 0.5))
n = canvas.mask_pixels()
C.click_button(app, dock._fmt_chk["nifti"]); C.click_button(app, dock._image_chk)
C.click_button(app, dock._save_btn)
st = C.wait_status(app, dock)
check("nifti item saved (png+nifti, image+mask)", st == "Saved 4 file(s) → vidi_output/ (png, nifti)", st)
import nibabel as nib
ni = nib.load(os.path.join(C.SCRATCH, "vidi_output", "nifti", "C_image.nii.gz"))
check("saved nifti image equals displayed slice", np.array_equal(np.asarray(ni.dataobj), canvas.displayed_pixels().T[..., None]), f"{ni.shape}")
# next → RGBA PNG item
C.click_button(app, dock._next_btn)
check("PNG item loads", H.wait_loaded(app, cell) and cell.series_data().meta.series_dir == PNG)
px = canvas.displayed_pixels()
check("PNG displayed as 2-D float32 (296x252 → H=252, W=296)", px.shape == (252, 296) and px.dtype == np.float32, f"{px.shape} {px.dtype}")
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.6, 0.6))
C.click_button(app, dock._save_btn)
st = C.wait_status(app, dock)
check("png item saved", st == "Saved 4 file(s) → vidi_output/ (png, nifti)", st)
from PIL import Image
pm = np.array(Image.open(os.path.join(C.SCRATCH, "vidi_output", "png", "3_mask.png")))
check("png item mask exact", np.array_equal(pm, canvas.mask() * 255))
sys.exit(C.finish(win, app))
