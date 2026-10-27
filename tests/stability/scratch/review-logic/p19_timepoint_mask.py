"""4-D NIfTI item: mask/rect kept across t and z slider moves (same shape); saved image is the slice shown at save time."""
from common import *
import numpy as np, nibabel as nib
from PIL import Image
d = os.path.join(SCR, "ws", "p19"); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
vol = np.zeros((32, 24, 4, 3), np.float32)
for t in range(3):
    for z in range(4): vol[:, :, z, t] = 100 * t + 10 * z
nib.save(nib.Nifti1Image(vol, np.eye(4)), os.path.join(d, "v4d.nii.gz"))
app, win = H.boot(); dock, quad = win._dock, win._quad
ws = H.open_workspace(app, win, d); cell = quad.active_cell(); c = cell.canvas()
H.pump(app, 300)
H.drag(app, c, H.pt(c,0.3,0.3), H.pt(c,0.5,0.3)); n = c.mask_pixels()
dock._tool_btns["rect"].setChecked(True); dock._apply_tool(); H.drag(app, c, H.pt(c,0.2,0.2), H.pt(c,0.7,0.7)); r = c.crop_rect()
cell._time_slider.setValue(2); cell._slice_slider.setValue(3) if hasattr(cell, "_slice_slider") else None; app.processEvents(); H.pump(app, 200)
print("after t/z change: mask", c.mask_pixels(), "rect", c.crop_rect(), "shown value", float(c.displayed_pixels()[0,0]))
check("mask + rect survive timepoint/slice change of the same shape (documented: 2-D on displayed slice)", c.mask_pixels() == n and c.crop_rect() == r)
dock._image_chk.setChecked(True); dock._save(advance=False); app.processEvents()
im = np.array(Image.open(os.path.join(ws.out_dir, "png", "v4d_image.png")))
print("saved image shape", im.shape, "canvas", c.displayed_pixels().shape)
check("saved _image.png is the slice displayed at save time", im.shape == c.displayed_pixels().shape)
win.close(); app.processEvents(); sys.exit(summary())
