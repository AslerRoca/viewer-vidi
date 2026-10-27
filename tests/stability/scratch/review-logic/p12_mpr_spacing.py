"""3-D DICOM item shown as a reformatted (coronal) plane: exported NIfTI spacing uses pixel_spacing for rows although rows are slices."""
from common import *
import numpy as np, nibabel as nib, glob
src = sorted(os.listdir(MR))[:20]
d = os.path.join(SCR, "ws", "p12"); shutil.rmtree(d, ignore_errors=True); os.makedirs(os.path.join(d, "series"))
for f in src: shutil.copy(os.path.join(MR, f), os.path.join(d, "series", f))
app, win = H.boot(); dock, quad = win._dock, win._quad
from viewer_vidi import workspace as W
imgs, _ = W.probe_workspace(d)
check("20 extensionless DICOM files are items", len(imgs) == 20, str(len(imgs)))
# each file is a 2-D item; a 3-D view needs the directory loaded in the panel → load dir via tree path, then the item mismatch guard applies.
cell = quad.active_cell(); ok = H.load_file(app, cell, os.path.join(d, "series"))
t0 = time.time()
while time.time() - t0 < 60 and (cell._loaded_mask is None or not cell._loaded_mask.all() if hasattr(cell._loaded_mask, 'all') else True):
    app.processEvents(); time.sleep(0.02)
    if cell._vol is not None and cell.series_data() is not None and cell.series_data().series_type.name == "S3D": break
sd = cell.series_data(); print("series", sd.series_type, "px", sd.pixel_spacing, "slice", sd.slice_spacing, "acq", sd.acq_plane)
check("directory loads as a 3-D series", sd.series_type.name == "S3D")
cell._set_view("CORONAL" if sd.acq_plane != "CORONAL" else "AXIAL"); app.processEvents()
c = cell.canvas(); shape = c.displayed_pixels().shape; print("reformatted displayed shape", shape, "view", cell._view_mode)
# Save through the exporter exactly as the dock does (the dock refuses: item ≠ dir); replicate dock spacing choice
from viewer_vidi.annotation_export import ExportInput, ExportOptions, export_item
m = np.zeros(shape, np.uint8); m[2:5, 2:5] = 1
out = os.path.join(d, "out"); shutil.rmtree(out, ignore_errors=True)
inp = ExportInput(stem="mpr", pixels=c.displayed_pixels(), wc=1, ww=1, mask=m, spacing=(float(sd.pixel_spacing[0]), float(sd.pixel_spacing[1])))
export_item(out, inp, ExportOptions(formats=("nifti",), save_image=True))
zo = nib.load(os.path.join(out, "nifti", "mpr_image.nii.gz")).header.get_zooms()[:2]
exp_row = sd.slice_spacing; print("exported zooms (x=col,y=row)", zo, "true row spacing (slice)", exp_row)
check("reformatted plane: exported row spacing equals slice spacing", abs(float(zo[1]) - exp_row) < 1e-3, f"got row {zo[1]} expected {exp_row}")
win.close(); app.processEvents(); sys.exit(summary())
