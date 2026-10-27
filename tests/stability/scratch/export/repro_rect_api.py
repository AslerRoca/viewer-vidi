"""Repro (API level; the canvas clamps rects so the GUI cannot produce these): export_item does not validate rect —
out-of-range rects are clipped silently by numpy (crop smaller than the rect, NIfTI origin still = rect origin);
reversed / negative / zero-area rects raise from PIL AFTER earlier products were already written (no manifest row)."""
import os, sys, shutil; sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H; H.register_package()
import numpy as np, nibabel as nib
from PIL import Image
from viewer_vidi.annotation_export import ExportInput, ExportOptions, export_item
D = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/export/out/rectapi"
px = np.arange(20 * 30, dtype=np.float32).reshape(20, 30); m = np.zeros((20, 30), np.uint8); m[5:10, 5:10] = 1
for rect in ((20, 10, 40, 30), (-5, -5, 10, 10), (10, 2, 5, 18), (5, 5, 5, 5)):
    shutil.rmtree(D, ignore_errors=True)
    try:
        w = export_item(D, ExportInput("r", px, 300, 600, mask=m, rect=rect), ExportOptions(formats=("png", "nifti")))
        roi = np.array(Image.open(os.path.join(D, "png", "r_roi.png"))); ni = nib.load(os.path.join(D, "nifti", "r_roi.nii.gz"))
        print(f"rect {rect}: ok, roi png shape {roi.shape}, nifti shape {ni.shape} origin {ni.affine[:2,3].tolist()}")
    except Exception as e:
        left = sorted(os.listdir(os.path.join(D, "png"))) if os.path.isdir(os.path.join(D, "png")) else []
        print(f"rect {rect}: {type(e).__name__}: {e}; files already written: {left}")
