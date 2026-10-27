"""canvasgeom lens, part 3: 3-D NIfTI — coronal/sagittal aspect mapping, crop bounds,
mask persistence across slice scroll + save of slice N with a mask drawn on slice M."""
import os, sys, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import numpy as np
from PyQt5.QtCore import Qt, QPoint
from matplotlib.path import Path as MplPath
import nibabel as nib

D = os.path.dirname(os.path.abspath(__file__))
NII = "/media/zsk/ressd/research/alldata_backup/Tongyu_Wang/radiology_qingyi/qingyi/+C/2035104/C.nii"
WS = os.path.join(D, "ws_nii"); shutil.rmtree(os.path.join(WS, "vidi_output"), ignore_errors=True)

app, win = H.boot()
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
ws = H.open_workspace(app, win, WS, mode="list", list_file=os.path.join(WS, "list.txt"))
check("list workspace with C.nii loads into the active panel", cell.series_data() is not None and canvas.displayed_pixels() is not None and canvas.displayed_pixels().shape == (288, 384), str(canvas.displayed_pixels().shape if canvas.displayed_pixels() is not None else None))
check("mode after workspace load is paint", canvas.wl_mode() == "paint", canvas.wl_mode())
vol = cell._vol
check("volume (Z,Y,X) = (56,288,384)", vol.shape == (56, 288, 384), str(vol.shape))
z0 = cell._slice_slider.value()
check("starts at mid slice", z0 == 28, str(z0))

def ipt(ix, iy):
    r = canvas._dest_rect(); h, w = canvas.displayed_pixels().shape
    return QPoint(int(r.x() + (ix + 0.5) * r.width() / w), int(r.y() + (iy + 0.5) * r.height() / h))
def expected_fill(verts, shape):
    h, w = shape; yy, xx = np.mgrid[0:h, 0:w]
    return MplPath(verts).contains_points(np.c_[xx.ravel() + 0.5, yy.ravel() + 0.5]).reshape(h, w)

# ── 1. mask persistence across slice scroll (axial) ─────────────────────────
tool(dock, "paint"); dock._brush_spin.setValue(10); app.processEvents()
H.drag(app, canvas, H.pt(canvas, 0.3, 0.5), H.pt(canvas, 0.7, 0.5), steps=8)
m28 = canvas.mask().copy(); n28 = canvas.mask_pixels()
px28 = canvas.displayed_pixels().copy()
check("stroke on slice 28", n28 > 0)
cell._scroll_slice(-120); app.processEvents()      # wheel down → slice+1
cell._slice_slider.setValue(10); app.processEvents()
check("slider moved to slice 10", cell._cur_z == 10 and cell._slice_slider.value() == 10, f"cur_z={cell._cur_z}")
px10 = canvas.displayed_pixels()
check("pixels changed to slice 10", not np.array_equal(px10, px28) and np.array_equal(px10, vol[10]))
check("mask drawn on slice 28 PERSISTS on slice 10 (same shape) — documented 2-D behaviour", np.array_equal(canvas.mask(), m28), f"n={canvas.mask_pixels()}")
check("_mask_nonempty still True after scroll", canvas._mask_nonempty)
inv(canvas, "slice scroll")
# undo while on slice 10 restores the pre-stroke (empty) mask
check("undo on slice 10 undoes the slice-28 stroke", canvas.undo_annotation() and canvas.mask_pixels() == 0)
H.drag(app, canvas, H.pt(canvas, 0.3, 0.5), H.pt(canvas, 0.7, 0.5), steps=8)   # redraw on slice 10 … then move away again
m10 = canvas.mask().copy()
cell._slice_slider.setValue(40); app.processEvents()
check("now on slice 40 with the slice-10 mask", cell._cur_z == 40 and np.array_equal(canvas.mask(), m10))
# save: nifti image + mask, no crop
for k, chk in dock._fmt_chk.items(): chk.setChecked(k == "nifti")
dock._mask_chk.setChecked(True); dock._crop_chk.setChecked(False); dock._image_chk.setChecked(True); app.processEvents()
seen = H.auto_close_dialogs(app, 300)
dock._save(advance=False); app.processEvents(); H.pump(app, 400)
check("save succeeded without dialogs", not seen and dock._ws.items[0].done, f"dialogs={seen} status={dock._status_lbl.text()}")
outd = os.path.join(WS, "vidi_output", "nifti")
stem = dock._ws.items[0].stem
img_p, mask_p = os.path.join(outd, f"{stem}_image.nii.gz"), os.path.join(outd, f"{stem}_mask.nii.gz")
check("nifti image + mask written", os.path.isfile(img_p) and os.path.isfile(mask_p), str(os.listdir(outd) if os.path.isdir(outd) else None))
if os.path.isfile(img_p):
    saved = np.asarray(nib.load(img_p).dataobj)[:, :, 0].T
    savedm = np.asarray(nib.load(mask_p).dataobj)[:, :, 0].T
    check("saved image is slice 40 (the DISPLAYED slice at save time), not slice 10 where the mask was drawn",
          np.allclose(saved, vol[40]) and not np.allclose(saved, vol[10]), f"match40={np.allclose(saved, vol[40])} match10={np.allclose(saved, vol[10])}")
    check("saved mask is the slice-10 drawing", np.array_equal(savedm > 0, m10 > 0))
    from viewer_vidi import workspace as W
    man = W.read_manifest(os.path.join(WS, "vidi_output", "manifest.csv"))
    check("manifest row has no slice index column (informational)", True, f"columns={list(man[stem].keys())}")

# ── 2. CORONAL: aspect != 1 ─────────────────────────────────────────────────
cell._set_view("CORONAL"); app.processEvents(); H.pump(app, 100)
pxc = canvas.displayed_pixels()
check("coronal slice shape (56, 384)", pxc.shape == (56, 384), str(pxc.shape))
check("coronal aspect = dz/dx ≈ 3.53", abs(canvas._aspect - 4.0 / 1.1328125) < 1e-3, f"{canvas._aspect}")
check("orientation change (shape change) resets mask + rect silently (informational)", canvas.mask_pixels() == 0 and canvas.crop_rect() is None and canvas._undo == [])
inv(canvas, "coronal switch")
r = canvas._dest_rect()
check("dest rect honours aspect (h/w ≈ 56*3.53/384)", abs(r.height() / r.width() - (56 * canvas._aspect) / 384) < 0.02, f"{r} ratio={r.height()/r.width():.3f}")
sx, sy = r.width() / 384, r.height() / 56
check("screen px per image px: y ≈ 3.53 × x", abs(sy / sx - canvas._aspect) < 0.05, f"sx={sx:.3f} sy={sy:.3f}")
tool(dock, "paint"); dock._brush_spin.setValue(5); app.processEvents()
disk5 = int(((np.arange(-5, 6)[:, None] ** 2 + np.arange(-5, 6)[None, :] ** 2) <= 25).sum())
P = ipt(200, 28)
H.click(canvas, P); app.processEvents()
c = centroid(canvas.mask()); exp = canvas._image_coords(P.x(), P.y()); bb = bbox(canvas.mask())
check("coronal paint click: centroid == _image_coords", c is not None and abs(c[0]-exp[0]) < 0.51 and abs(c[1]-exp[1]) < 0.51 and canvas.mask_pixels() == disk5, f"exp={exp} c={c} n={canvas.mask_pixels()}/{disk5}")
check("coronal footprint is circular in IMAGE px (11x11) → on screen an ellipse ~3.5× taller than the brush cursor circle (ux, informational)", bb is not None and (bb[2]-bb[0]+1, bb[3]-bb[1]+1) == (11, 11),
      f"bbox_img={bb} screen footprint ≈ {11*sx:.0f}x{11*sy:.0f} px, cursor circle radius drawn = {5*sx:.1f} px")
inv(canvas, "coronal paint")
# paint near the bottom edge (row 55) clips to 56 rows
H.click(canvas, ipt(100, 55)); app.processEvents()
check("coronal paint at last row clips", bbox(canvas.mask())[3] == 55)
inv(canvas, "coronal edge paint")
# polygon on coronal
canvas.clear_annotations(); canvas._undo = []
tool(dock, "poly"); app.processEvents()
Pp = [ipt(50, 5), ipt(300, 10), ipt(250, 50), ipt(80, 45)]
verts = [canvas._image_coords(p.x(), p.y()) for p in Pp]
for p in Pp: H.click(canvas, p)
H.dclick(canvas, Pp[-1]); app.processEvents()
exp = expected_fill([(x+0.5, y+0.5) for x, y in verts], pxc.shape)
agree = ((canvas.mask() > 0) == exp).mean()
check("coronal polygon fill matches reference of _image_coords vertices", canvas.mask_pixels() > 500 and agree > 0.99, f"verts={verts} n={canvas.mask_pixels()} ref={int(exp.sum())} agree={agree:.4f}")
inv(canvas, "coronal polygon")
# rect on coronal: bounds vs (384, 56)
tool(dock, "rect"); app.processEvents()
H.drag(app, canvas, QPoint(r.x() - 30, r.y() - 30), QPoint(r.x() + r.width() + 30, r.y() + r.height() + 30))
check("coronal rect from beyond all edges clips to (0,0,384,56)", canvas.crop_rect() == (0, 0, 384, 56), str(canvas.crop_rect()))
a, b = ipt(100, 10), ipt(300, 40)
H.drag(app, canvas, a, b)
ai, bi = canvas._image_coords(a.x(), a.y()), canvas._image_coords(b.x(), b.y())
check("coronal rect equals _image_coords end points", canvas.crop_rect() == (ai[0], ai[1], bi[0]+1, bi[1]+1), f"{canvas.crop_rect()} a={ai} b={bi}")
inv(canvas, "coronal rect")
# coronal slice scroll keeps mask/rect (same shape)
mc = canvas.mask().copy(); rc = canvas.crop_rect()
cell._slice_slider.setValue(cell._slice_slider.value() + 5); app.processEvents()
check("coronal slice scroll keeps mask and rect", np.array_equal(canvas.mask(), mc) and canvas.crop_rect() == rc and canvas.displayed_pixels().shape == (56, 384))
inv(canvas, "coronal scroll")
# zoom + pan on coronal then paint
for _ in range(3): canvas.zoom_wheel(+120)
H.drag(app, canvas, wpt(canvas, 150, 150), wpt(canvas, 100, 190), steps=4, button=Qt.RightButton)
tool(dock, "paint"); app.processEvents()
canvas.clear_annotations()
P = H.pt(canvas, 0.4, 0.5); H.click(canvas, P); app.processEvents()
c = centroid(canvas.mask()); exp = canvas._image_coords(P.x(), P.y())
check("coronal zoom+pan paint centroid == _image_coords", c is not None and abs(c[0]-exp[0]) < 0.51 and abs(c[1]-exp[1]) < 0.51, f"exp={exp} c={c} zoom={canvas._zoom:.2f} pan=({canvas._pan_x},{canvas._pan_y})")
inv(canvas, "coronal zoom+pan paint")

# ── 3. SAGITTAL ──────────────────────────────────────────────────────────────
cell._set_view("SAGITTAL"); app.processEvents(); H.pump(app, 100)
pxs = canvas.displayed_pixels()
check("sagittal slice shape (56, 288)", pxs.shape == (56, 288), str(pxs.shape))
check("sagittal switch resets annotations, zoom/pan preserved (reset_view=False)", canvas.mask_pixels() == 0 and canvas.crop_rect() is None and canvas._zoom > 1.0, f"zoom={canvas._zoom:.2f}")
inv(canvas, "sagittal switch")
canvas.set_image(pxs, canvas._aspect, reset_view=True)
tool(dock, "paint"); app.processEvents()
P = ipt(144, 20); H.click(canvas, P); app.processEvents()
c = centroid(canvas.mask()); exp = canvas._image_coords(P.x(), P.y())
check("sagittal paint centroid == _image_coords", c is not None and abs(c[0]-exp[0]) < 0.51 and abs(c[1]-exp[1]) < 0.51 and canvas.mask_pixels() == disk5, f"exp={exp} c={c} n={canvas.mask_pixels()}")
tool(dock, "rect"); app.processEvents()
r = canvas._dest_rect()
H.drag(app, canvas, QPoint(r.x() + r.width()//2, r.y() - 40), QPoint(r.x() + r.width() + 40, r.y() + r.height()//2))
rc = canvas.crop_rect()
check("sagittal rect clipped inside (56, 288)", rc is not None and rc[1] == 0 and rc[2] == 288 and 0 <= rc[0] < rc[2] and 0 < rc[3] <= 56, str(rc))
inv(canvas, "sagittal rect")
# Save with the sagittal reformat: pixels (56,288) and mask saved consistently?
for k, chk in dock._fmt_chk.items(): chk.setChecked(k == "png")
dock._crop_chk.setChecked(True); app.processEvents()
seen = H.auto_close_dialogs(app, 300)
dock._save(advance=False); app.processEvents(); H.pump(app, 400)
check("save on a sagittal reformat succeeds", not seen, f"dialogs={seen} status={dock._status_lbl.text()}")
from PIL import Image
pm = os.path.join(WS, "vidi_output", "png", f"{stem}_mask.png")
if os.path.isfile(pm):
    im = np.array(Image.open(pm))
    check("saved sagittal mask has the reformat shape (56, 288)", im.shape == (56, 288) and (im == 255).sum() == canvas.mask_pixels(), f"{im.shape} n={(im==255).sum()}")
    roi = np.array(Image.open(os.path.join(WS, "vidi_output", "png", f"{stem}_roi.png")))
    check("saved sagittal roi crop has rect shape", roi.shape == (rc[3]-rc[1], rc[2]-rc[0]), f"{roi.shape} rect={rc}")

# ── 4. back to AXIAL: fresh mask; same-shape re-render keeps it ──────────────
cell._set_view("AXIAL"); app.processEvents(); H.pump(app, 100)
check("axial again: (288,384), annotations reset", canvas.displayed_pixels().shape == (288, 384) and canvas.mask_pixels() == 0 and canvas.crop_rect() is None)
inv(canvas, "axial again")

win.close(); app.processEvents()
sys.exit(1 if summary() else 0)
