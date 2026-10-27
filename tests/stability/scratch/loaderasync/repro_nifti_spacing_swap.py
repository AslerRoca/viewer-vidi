"""Minimal repro: NIfTI items with anisotropic in-plane spacing export a swapped affine
(and, for 2-D NIfTI, swapped axes). No Qt needed for the loader part; the dock path is
the same ExportInput(spacing=(sd.pixel_spacing[0], sd.pixel_spacing[1])).

 - 3-D NIfTI X=40,Y=30,Z=5, zooms (0.5, 2.0, 3.0): displayed slice is (Y,X)=(30,40) but
   sd.pixel_spacing = (zooms[0], zooms[1]) = (0.5, 2.0) is read as (row_mm, col_mm) → the
   exported .nii.gz gets zooms (2.0, 0.5) instead of (0.5, 2.0).
 - 2-D NIfTI X=40,Y=30: the loader shows it untransposed (rows = X) so the export (which
   assumes rows = Y) writes shape (30,40,1): x/y swapped relative to the source file.

Run: QT_QPA_PLATFORM=offscreen timeout 300 ~/miniconda3/envs/viewer_vidi/bin/python repro_nifti_spacing_swap.py
"""
import os, sys, shutil
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
import numpy as np, nibabel as nib

D = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/loaderasync/fx/repro_nii"
shutil.rmtree(D, ignore_errors=True); os.makedirs(D)
a3 = np.arange(40 * 30 * 5, dtype=np.float32).reshape(40, 30, 5)
nib.save(nib.Nifti1Image(a3, np.diag([0.5, 2.0, 3.0, 1.0])), os.path.join(D, "n3d.nii.gz"))
a2 = np.arange(40 * 30, dtype=np.float32).reshape(40, 30)
nib.save(nib.Nifti1Image(a2, np.diag([0.5, 2.0, 1.0, 1.0])), os.path.join(D, "n2d.nii.gz"))

app, win = H.boot()
dock, cell = win._dock, win._quad.active_cell(); canvas = cell.canvas()
ws = H.open_workspace(app, win, D)
dock._fmt_chk["nifti"].setChecked(True); dock._image_chk.setChecked(True)
for stem in ("n3d", "n2d"):
    dock._load_index([it.stem for it in ws.items].index(stem)); H.wait_loaded(app, cell)
    sd = cell.series_data(); px = canvas.displayed_pixels()
    dock._save(advance=False); app.processEvents()
    out = nib.load(os.path.join(D, "vidi_output", "nifti", f"{stem}_image.nii.gz"))
    print(f"{stem}: displayed (rows, cols)={px.shape}  sd.pixel_spacing(row,col)={sd.pixel_spacing}  "
          f"source shape={nib.load(os.path.join(D, stem + '.nii.gz')).shape} zooms(0.5, 2.0[, 3.0])  "
          f"-> exported shape={out.shape} zooms={tuple(float(z) for z in out.header.get_zooms())}")
win.close()
