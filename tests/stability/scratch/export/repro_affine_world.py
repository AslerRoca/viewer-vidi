"""Repro: a mask drawn on slice z of a 3-D NIfTI is saved with affine diag(col,row,1,1) and origin 0 — the source
volume's orientation/translation (and the slice's z position) are dropped, so the saved mask does not overlay the
source in world space (it is index-aligned only)."""
import os, sys, shutil; sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H; H.register_package()
import numpy as np, nibabel as nib
from viewer_vidi.annotation_export import ExportInput, ExportOptions, export_item
SRC = "/media/zsk/ressd/research/alldata_backup/Tongyu_Wang/radiology_qingyi/qingyi/+C/2035104/C.nii"
D = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/export/out/affine"; shutil.rmtree(D, ignore_errors=True)
app, win = H.boot(); cell = win._quad.active_cell(); canvas = cell.canvas()
H.load_file(app, cell, SRC); sd = cell.series_data(); z = cell._cur_z
m = np.zeros_like(canvas.mask()); m[100:140, 150:200] = 1
export_item(D, ExportInput("c", canvas.displayed_pixels(), *canvas.wl(), mask=m, spacing=tuple(map(float, sd.pixel_spacing))), ExportOptions(formats=("nifti",)))
src = nib.load(SRC); out = nib.load(os.path.join(D, "nifti", "c_mask.nii.gz"))
print("source axcodes", nib.aff2axcodes(src.affine), "slice z =", z); print("source affine:\n", np.round(src.affine, 3)); print("saved mask affine:\n", out.affine)
ctr = np.array([175, 120, 0, 1.0])
print("mask voxel (175,120) world in saved file:", (out.affine @ ctr)[:3], " same voxel on slice z in source:", (src.affine @ np.array([175, 120, z, 1.0]))[:3])
win.close()
