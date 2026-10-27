"""Anisotropic 3-D NIfTI item: sd.pixel_spacing is (zooms[0], zooms[1]) but the displayed slice is (Y, X) → exported affine swaps x/y spacing.
Also: coronal (reformatted) view of the same item saved through the dock → row spacing should be the z zoom."""
from common import *
import numpy as np, nibabel as nib
d = os.path.join(SCR, "ws", "p11"); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
X, Y, Z = 40, 30, 5
vol = (np.random.RandomState(0).rand(X, Y, Z) * 1000).astype(np.float32)
img3 = nib.Nifti1Image(vol, np.diag([0.5, 2.0, 3.0, 1.0])); img3.header.set_zooms((0.5, 2.0, 3.0)); nib.save(img3, os.path.join(d, "aniso3d.nii.gz"))
app, win = H.boot(); dock, quad = win._dock, win._quad
ws = H.open_workspace(app, win, d); cell = quad.active_cell(); c = cell.canvas(); H.pump(app, 300)
dock._fmt_chk["nifti"].setChecked(True); dock._image_chk.setChecked(True)
sd = cell.series_data(); shown = c.displayed_pixels()
print("displayed (H,W)=", shown.shape, "sd.pixel_spacing=", sd.pixel_spacing, "slice_spacing=", sd.slice_spacing, "view", cell._view_mode)
# identify which source axes the displayed rows/cols are: rows must be Y (30) and cols X (40)
check("3-D NIfTI displays rows=Y(30), cols=X(40)", shown.shape == (Y, X), str(shown.shape))
check("sd.pixel_spacing should be (row_mm, col_mm) = (Y zoom 2.0, X zoom 0.5)", tuple(sd.pixel_spacing) == (2.0, 0.5), f"got {sd.pixel_spacing} (loader stores zooms[0],zooms[1])")
H.drag(app, c, H.pt(c,0.3,0.3), H.pt(c,0.6,0.3))
dock._save(advance=False); app.processEvents()
out = nib.load(os.path.join(ws.out_dir, "nifti", "aniso3d_image.nii.gz"))
zo = tuple(round(float(z), 3) for z in out.header.get_zooms()[:2]); arr = np.asarray(out.dataobj)[:, :, 0]
# find the matching source z slice (any flip) to prove exported X axis == source X axis
match = None
for z in range(Z):
    for name, s in (("id", vol[:, :, z]), ("flipud", vol[::-1, :, z]), ("fliplr", vol[:, ::-1, z]), ("both", vol[::-1, ::-1, z])):
        if arr.shape == s.shape and np.allclose(arr, s): match = (z, name)
print("exported shape", arr.shape, "zooms", zo, "matches source z/flip:", match)
check("exported data axes = source (X,Y) axes", match is not None, str(arr.shape))
check("exported NIfTI zooms equal source (0.5, 2.0)", zo == (0.5, 2.0), f"got {zo} → swapped")
# coronal reformat of the same item through the dock
cell._set_view("CORONAL"); app.processEvents(); H.pump(app, 200)
shown2 = c.displayed_pixels(); print("coronal displayed (H,W)=", shown2.shape, "(rows should be Z=5)")
H.drag(app, c, H.pt(c,0.3,0.3), H.pt(c,0.6,0.3))
dock._save(advance=False); app.processEvents()
out2 = nib.load(os.path.join(ws.out_dir, "nifti", "aniso3d_image.nii.gz"))
zo2 = tuple(round(float(z), 3) for z in out2.header.get_zooms()[:2]); print("coronal export zooms (x=col,y=row)", zo2, "shape", out2.shape)
check("coronal view export: row spacing is the z zoom 3.0 (x spacing 0.5)", zo2 == (0.5, 3.0), f"got {zo2}")
check("coronal view export: shape is (X=40, Z=5, 1)", out2.shape == (40, 5, 1), str(out2.shape))
win.close(); app.processEvents(); sys.exit(summary())
