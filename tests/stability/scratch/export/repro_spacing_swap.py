"""Repro: export writes NIfTI zooms = (col_mm, row_mm) (NIfTI x=columns, correct) but loader._run_nifti_load reads
zooms[0] as row spacing, so a reloaded export shows pixel_spacing swapped and a second export swaps the file's zooms."""
import os, sys, shutil; sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H; H.register_package()
import numpy as np, nibabel as nib
from viewer_vidi.annotation_export import ExportInput, ExportOptions, export_item
D = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/export/out/swap"; shutil.rmtree(D, ignore_errors=True)
px = np.arange(20 * 30, dtype=np.float32).reshape(20, 30)       # 20 rows x 30 cols
export_item(D, ExportInput("s", px, 300, 600, spacing=(0.5, 0.25)), ExportOptions(formats=("nifti",), save_image=True))   # row_mm=0.5, col_mm=0.25
p = os.path.join(D, "nifti", "s_image.nii.gz"); im = nib.load(p)
print("file shape (x,y,z):", im.shape, "zooms:", tuple(float(v) for v in im.header.get_zooms()))
app, win = H.boot(); cell = win._quad.active_cell()
H.load_file(app, cell, p); sd = cell.series_data()
print("reloaded in viewer: rows,cols =", sd.rows, sd.cols, " pixel_spacing (row_mm, col_mm) =", sd.pixel_spacing, " expected (0.5, 0.25)")
export_item(D + "2", ExportInput("s", cell.canvas().displayed_pixels(), 300, 600, spacing=tuple(map(float, sd.pixel_spacing))), ExportOptions(formats=("nifti",), save_image=True))
print("re-exported zooms:", tuple(float(v) for v in nib.load(os.path.join(D + "2", "nifti", "s_image.nii.gz")).header.get_zooms()), " first export zooms:", tuple(float(v) for v in im.header.get_zooms()))
win.close()
