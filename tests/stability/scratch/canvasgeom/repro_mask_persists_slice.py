"""Repro: mask drawn on slice 10 of a 3-D NIfTI persists while scrolling; Save on slice 40 writes
slice-40 pixels + the slice-10 mask; manifest records no slice index."""
import os, sys, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import nibabel as nib
D = os.path.dirname(os.path.abspath(__file__)); WS = os.path.join(D, "ws_nii")
shutil.rmtree(os.path.join(WS, "vidi_output"), ignore_errors=True)
app, win = H.boot(); dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
H.open_workspace(app, win, WS, mode="list", list_file=os.path.join(WS, "list.txt"))
cell._slice_slider.setValue(10); app.processEvents()
tool(dock, "paint"); dock._brush_spin.setValue(10)
H.drag(app, canvas, H.pt(canvas, 0.3, 0.5), H.pt(canvas, 0.7, 0.5)); m10 = canvas.mask().copy()
cell._slice_slider.setValue(40); app.processEvents()
print("mask px on slice 40 after drawing on slice 10:", canvas.mask_pixels())
for k, chk in dock._fmt_chk.items(): chk.setChecked(k == "nifti")
dock._image_chk.setChecked(True); dock._mask_chk.setChecked(True)
dock._save(advance=False); app.processEvents()
stem = dock._ws.items[0].stem
img = np.asarray(nib.load(os.path.join(WS, "vidi_output", "nifti", f"{stem}_image.nii.gz")).dataobj)[:, :, 0].T
msk = np.asarray(nib.load(os.path.join(WS, "vidi_output", "nifti", f"{stem}_mask.nii.gz")).dataobj)[:, :, 0].T
print("saved image == slice 40:", np.allclose(img, cell._vol[40]), "| == slice 10:", np.allclose(img, cell._vol[10]))
print("saved mask == slice-10 drawing:", np.array_equal(msk > 0, m10 > 0))
print(open(os.path.join(WS, "vidi_output", "manifest.csv")).read())
win.close()
