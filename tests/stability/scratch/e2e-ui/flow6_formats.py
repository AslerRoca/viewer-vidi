"""Flow 6: JPEG + NIfTI only, Mask unticked, Original ticked → exact file set (+ content variants)."""
import os, sys, shutil
import e2e_common as C
from e2e_common import check, H
import numpy as np
import nibabel as nib
from PIL import Image

ROOT = os.path.join(C.FX, "ws_fmt")      # 3.png (RGBA) + 1 DICOM
OUT = os.path.join(ROOT, "vidi_output")
shutil.rmtree(OUT, ignore_errors=True)

app, win = H.boot()
dock, quad = win._dock, win._quad
C.click_button(app, win._ws_btn)
cell = quad.active_cell(); canvas = cell.canvas()
seen = C.open_dir_via_ui(app, win, ROOT)
ws = dock.workspace()
check("2 items: 3 (png) then dcm", ws is not None and [it.stem for it in ws.items] == ["3", "bpd3_20100422_1"], str(ws and [it.stem for it in ws.items]))
check("item 1 loaded", H.wait_loaded(app, cell))
stem = ws.items[0].stem

# formats: JPEG + NIfTI only; content: Mask off, Crop on, Original on
C.click_button(app, dock._fmt_chk["png"]); C.click_button(app, dock._fmt_chk["jpeg"]); C.click_button(app, dock._fmt_chk["nifti"])
C.click_button(app, dock._mask_chk); C.click_button(app, dock._image_chk)
check("ticks: png off, jpeg on, nifti on, mask off, crop on, original on",
      not dock._fmt_chk["png"].isChecked() and dock._fmt_chk["jpeg"].isChecked() and dock._fmt_chk["nifti"].isChecked()
      and not dock._mask_chk.isChecked() and dock._crop_chk.isChecked() and dock._image_chk.isChecked())
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.5, 0.3))     # brush
n = canvas.mask_pixels()
C.click_button(app, dock._tool_btns["rect"])
H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.8, 0.8))
rect = canvas.crop_rect()
check("mask + rect present", n > 0 and rect is not None, f"{n} {rect}")
px = canvas.displayed_pixels().copy(); wc, ww = canvas.wl(); inv = canvas.invert()
C.click_button(app, dock._save_btn); st = C.wait_status(app, dock)
check("status: Saved 4 file(s) → vidi_output/ (jpeg, nifti)", st == "Saved 4 file(s) → vidi_output/ (jpeg, nifti)", st)
exp = sorted(["manifest.csv", f"jpeg/{stem}_image.jpg", f"jpeg/{stem}_roi.jpg", f"nifti/{stem}_image.nii.gz", f"nifti/{stem}_roi.nii.gz"])
check("exact file set (no png dir, no mask files)", C.out_files(OUT) == exp, str(C.out_files(OUT)))
x0, y0, x1, y1 = rect
nr = nib.load(os.path.join(OUT, "nifti", f"{stem}_roi.nii.gz"))
check("nifti roi == pixels crop .T[...,None]", np.array_equal(np.asarray(nr.dataobj), px[y0:y1, x0:x1].T[..., None]))
ji = np.array(Image.open(os.path.join(OUT, "jpeg", f"{stem}_image.jpg")))
from viewer_vidi.annotation_export import window_to_uint8
ref = window_to_uint8(px, wc, ww, inv).astype(np.int16)
check("jpeg image: shape ok, mean abs diff from 8-bit reference < 3 (q95)", ji.shape == px.shape and np.abs(ji.astype(np.int16) - ref).mean() < 3, f"{ji.shape} mad={np.abs(ji.astype(np.int16) - ref).mean():.2f}")
from viewer_vidi import workspace as W
r = W.read_manifest(os.path.join(OUT, "manifest.csv"))[stem]
check("manifest: formats 'jpeg nifti', 4 files, rect cols", r["formats"] == "jpeg nifti" and len(r["files"].split()) == 4 and (r["x0"], r["y1"]) == (str(x0), str(y1)), str(r))
check("manifest mask_pixels records canvas mask even though Mask was unticked (observe)", int(r["mask_pixels"]) == n, r["mask_pixels"])
check("item ✓", ws.items[0].done and C.list_texts(dock)[0].startswith("✓"))

# item 2: mask only (no rect), Mask unticked, Original unticked → nothing to save
C.click_button(app, dock._next_btn); check("item 2 loaded", H.wait_loaded(app, cell))
C.click_button(app, dock._image_chk)
C.click_button(app, dock._tool_btns["paint"])
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.5, 0.3))
C.click_button(app, dock._save_btn); st = C.wait_status(app, dock)
check("nothing-to-save status, item not done", st == "Nothing to save: draw a mask or a rectangle, or tick Original." and not ws.items[1].done, st)
check("no files written for item 2", all("bpd3" not in f for f in C.out_files(OUT)), str(C.out_files(OUT)))
# tick Mask, untick Crop, add rect → mask + roi_mask but no roi
C.click_button(app, dock._mask_chk); C.click_button(app, dock._crop_chk)
C.click_button(app, dock._tool_btns["rect"])
H.drag(app, canvas, H.pt(canvas, 0.25, 0.25), H.pt(canvas, 0.6, 0.6))
m2 = canvas.mask().copy(); r2 = canvas.crop_rect()
C.click_button(app, dock._save_btn); st = C.wait_status(app, dock)
check("Mask on / Crop off / rect: Saved 4 file(s)", st == "Saved 4 file(s) → vidi_output/ (jpeg, nifti)", st)
s2 = ws.items[1].stem
files2 = sorted(f for f in C.out_files(OUT) if s2 in f)
check("files: mask + roi_mask in jpeg & nifti, no roi/image", files2 == sorted([f"jpeg/{s2}_mask.jpg", f"jpeg/{s2}_roi_mask.jpg", f"nifti/{s2}_mask.nii.gz", f"nifti/{s2}_roi_mask.nii.gz"]), str(files2))
nm = nib.load(os.path.join(OUT, "nifti", f"{s2}_roi_mask.nii.gz"))
check("nifti roi_mask uint8 == mask crop", nm.get_data_dtype() == np.uint8 and np.array_equal(np.asarray(nm.dataobj), m2[r2[1]:r2[3], r2[0]:r2[2]].T[..., None]))
# untick every format → refusal status
for k in ("jpeg", "nifti"):
    C.click_button(app, dock._fmt_chk[k])
C.click_button(app, dock._save_btn); st = C.wait_status(app, dock)
check("no format ticked → 'Tick at least one format' status", st == "Tick at least one format (PNG / JPEG / NIfTI).", st)
sys.exit(C.finish(win, app))
