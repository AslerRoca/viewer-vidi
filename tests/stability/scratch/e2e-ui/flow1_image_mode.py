"""Flow 1: image mode on nested fixtures via 'Open directory…', annotate item 1
(brush + rect) and item 2 (polygon only), Ctrl+S each, verify output pixel-exactly."""
import os, sys, shutil
import e2e_common as C
from e2e_common import check, H
import numpy as np

ROOT = os.path.join(C.FX, "ws_nested")
OUT = os.path.join(ROOT, "vidi_output")
shutil.rmtree(OUT, ignore_errors=True)

app, win = H.boot()
dock, quad = win._dock, win._quad
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PIL import Image
import nibabel as nib
from viewer_vidi.annotation_export import window_to_uint8
from viewer_vidi import workspace as W

# ── open the dock with the toolbar button (public UI) ──
check("dock hidden at start", not dock.isVisible())
C.click_button(app, win._ws_btn)
check("toolbar Workspace button shows dock", dock.isVisible() and win._ws_btn.isChecked())

cell = quad.active_cell(); canvas = cell.canvas()
check("brush tool default + canvas in paint mode", dock._tool_btns["paint"].isChecked() and canvas.wl_mode() == "paint", canvas.wl_mode())

# ── Open directory… ──
seen = C.open_dir_via_ui(app, win, ROOT)
check("no dialog shown for pure image dir", seen == [], str(seen))
ws = dock.workspace()
check("workspace opened in image mode with 4 items", ws is not None and ws.mode == "image" and len(ws.items) == 4, str(ws and [it.stem for it in ws.items]))
stems = [it.stem for it in ws.items]
check("duplicate basename stems unique and folder-prefixed", len(set(stems)) == 4 and "a__bpd1_20100101_1" in stems and "b__sub__bpd1_20100101_1" in stems, str(stems))
check("list shows ○ for pending", all(t.startswith("○ ") for t in C.list_texts(dock)), str(C.list_texts(dock)))
check("ws label mentions IMAGE mode and item count", "IMAGE mode" in dock._ws_lbl.text() and "4 items" in dock._ws_lbl.text(), dock._ws_lbl.text())
check("first item loads into active panel", H.wait_loaded(app, cell) and os.path.abspath(cell.series_data().meta.series_dir) == ws.items[0].path)
check("count label 1/4 · 0 done", dock._count_lbl.text() == "1/4 · 0 done", dock._count_lbl.text())
check("Prev disabled, Next enabled on first item", not dock._prev_btn.isEnabled() and dock._next_btn.isEnabled())
check("tool re-applied after load", canvas.wl_mode() == "paint", canvas.wl_mode())

# ── item 1: brush + rect ──
px = canvas.displayed_pixels(); Hh, Ww = px.shape
check("mask allocated", canvas.mask() is not None and canvas.mask().shape == (Hh, Ww))
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.6, 0.35))
n1 = canvas.mask_pixels()
check("brush painted", n1 > 0, f"{n1}")
check("stats label shows mask px", f"mask {n1:,} px" in dock._stats_lbl.text(), dock._stats_lbl.text())
C.click_button(app, dock._tool_btns["rect"])
check("Rect button switches canvas mode", canvas.wl_mode() == "rect", canvas.wl_mode())
H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.7, 0.7))
rect = canvas.crop_rect()
check("rect set", rect is not None, str(rect))
check("stats label shows rect", rect is not None and f"rect ({rect[0]}, {rect[1]}) → ({rect[2]}, {rect[3]})" in dock._stats_lbl.text(), dock._stats_lbl.text())
check("invariants ok", not H.invariants(canvas), str(H.invariants(canvas)))

# all formats + Original, via checkbox clicks
for k in ("jpeg", "nifti"):
    C.click_button(app, dock._fmt_chk[k])
C.click_button(app, dock._image_chk)
check("formats all ticked", all(c.isChecked() for c in dock._fmt_chk.values()) and dock._image_chk.isChecked())

mask1 = canvas.mask().copy(); px1 = px.copy(); wc1, ww1 = canvas.wl(); inv1 = canvas.invert(); rect1 = rect
sp1 = cell.series_data().pixel_spacing
stem1 = ws.items[0].stem

# Ctrl+S → save & next
win.activateWindow(); app.processEvents()
C.ctrl_s(app, win, target=canvas)
st = C.wait_status(app, dock)
check("Ctrl+S saved (status text)", st.startswith("Saved 12 file(s)"), st)
check("item 1 marked ✓ and advanced to 2", ws.items[0].done and dock._index == 1 and C.list_texts(dock)[0] == "✓ " + stem1, str(C.list_texts(dock)))
check("count label 2/4 · 1 done", dock._count_lbl.text() == "2/4 · 1 done", dock._count_lbl.text())

# ── verify item 1 files pixel-exactly ──
pm = np.array(Image.open(os.path.join(OUT, "png", f"{stem1}_mask.png")))
check("png mask == mask*255", pm.dtype == np.uint8 and np.array_equal(pm, mask1 * 255))
x0, y0, x1, y1 = rect1
proi = np.array(Image.open(os.path.join(OUT, "png", f"{stem1}_roi.png")))
exp_roi = window_to_uint8(px1[y0:y1, x0:x1], wc1, ww1, inv1)
check("png roi == window_to_uint8(crop)", np.array_equal(proi, exp_roi), f"{proi.shape} vs {exp_roi.shape}")
prm = np.array(Image.open(os.path.join(OUT, "png", f"{stem1}_roi_mask.png")))
check("png roi_mask == mask crop*255", np.array_equal(prm, mask1[y0:y1, x0:x1] * 255))
pimg = np.array(Image.open(os.path.join(OUT, "png", f"{stem1}_image.png")))
check("png image == window_to_uint8(full)", np.array_equal(pimg, window_to_uint8(px1, wc1, ww1, inv1)))
jm = np.array(Image.open(os.path.join(OUT, "jpeg", f"{stem1}_mask.jpg")))
check("jpeg mask shape & near-binary", jm.shape == mask1.shape and ((jm > 127) == (mask1 > 0)).mean() > 0.99)
ni = nib.load(os.path.join(OUT, "nifti", f"{stem1}_image.nii.gz"))
check("nifti image == pixels.T[...,None] float32", ni.get_data_dtype() == np.float32 and np.array_equal(np.asarray(ni.dataobj), px1.T[..., None]), f"{ni.shape}")
check("nifti spacing in affine", np.allclose(np.diag(ni.affine)[:2], [sp1[1], sp1[0]]), f"{np.diag(ni.affine)[:2]} vs {sp1}")
nm = nib.load(os.path.join(OUT, "nifti", f"{stem1}_mask.nii.gz"))
check("nifti mask uint8 == mask.T[...,None]", nm.get_data_dtype() == np.uint8 and np.array_equal(np.asarray(nm.dataobj), mask1.T[..., None]))
nr = nib.load(os.path.join(OUT, "nifti", f"{stem1}_roi.nii.gz"))
check("nifti roi == crop.T[...,None]", np.array_equal(np.asarray(nr.dataobj), px1[y0:y1, x0:x1].T[..., None]))
check("nifti roi origin offset", np.allclose(nr.affine[:2, 3], [x0 * sp1[1], y0 * sp1[0]]), str(nr.affine[:2, 3]))
nrm = nib.load(os.path.join(OUT, "nifti", f"{stem1}_roi_mask.nii.gz"))
check("nifti roi_mask == mask crop.T", np.array_equal(np.asarray(nrm.dataobj), mask1[y0:y1, x0:x1].T[..., None]))
man = W.read_manifest(os.path.join(OUT, "manifest.csv"))
r1 = man.get(stem1)
check("manifest row 1 fields", r1 is not None and r1["source"] == ws.items[0].path and (r1["x0"], r1["y0"], r1["x1"], r1["y1"]) == tuple(map(str, rect1)) and int(r1["mask_pixels"]) == int(mask1.sum()) and r1["formats"] == "png jpeg nifti" and len(r1["files"].split()) == 12, str(r1))
check("manifest header columns", open(os.path.join(OUT, "manifest.csv")).readline().strip() == "stem,source,saved_at,mask_pixels,x0,y0,x1,y1,formats,files", open(os.path.join(OUT, "manifest.csv")).readline().strip())

# ── item 2: polygon only ──
check("item 2 loaded fresh", H.wait_loaded(app, cell) and canvas.mask_pixels() == 0 and canvas.crop_rect() is None and os.path.abspath(cell.series_data().meta.series_dir) == ws.items[1].path)
check("tool is still rect after advance (mode persists)", canvas.wl_mode() == "rect", canvas.wl_mode())
C.click_button(app, dock._tool_btns["poly"])
check("Polygon button → poly mode", canvas.wl_mode() == "poly")
for p in (H.pt(canvas, 0.2, 0.5), H.pt(canvas, 0.6, 0.5), H.pt(canvas, 0.6, 0.8), H.pt(canvas, 0.2, 0.8)):
    H.click(canvas, p)
app.processEvents()
check("4 vertices pending", len(canvas._poly_pts) == 4, str(canvas._poly_pts))
H.dclick(canvas, H.pt(canvas, 0.2, 0.8)); app.processEvents()
n2 = canvas.mask_pixels()
check("polygon filled, not fullscreen", n2 > 0 and not quad.is_fullscreen(), f"{n2}")
px2 = canvas.displayed_pixels().copy(); mask2 = canvas.mask().copy(); wc2, ww2 = canvas.wl(); inv2 = canvas.invert()
stem2 = ws.items[1].stem
# the polygon fills a bounding box subset — check the fill is the rect (0.2..0.6, 0.5..0.8) region approx
Hh2, Ww2 = px2.shape
ys, xs = np.nonzero(mask2)
check("polygon bbox approx", abs(xs.min() - 0.2 * Ww2) < 4 and abs(xs.max() - 0.6 * Ww2) < 4 and abs(ys.min() - 0.5 * Hh2) < 4 and abs(ys.max() - 0.8 * Hh2) < 4, f"x {xs.min()}..{xs.max()} y {ys.min()}..{ys.max()} of {Ww2}x{Hh2}")
C.ctrl_s(app, win, target=canvas)
st = C.wait_status(app, dock)
check("Ctrl+S saved item 2 (6 files: image+mask ×3)", st.startswith("Saved 6 file(s)"), st)
pm2 = np.array(Image.open(os.path.join(OUT, "png", f"{stem2}_mask.png")))
check("item2 png mask exact", np.array_equal(pm2, mask2 * 255))
check("item2 no roi files", not os.path.exists(os.path.join(OUT, "png", f"{stem2}_roi.png")) and not os.path.exists(os.path.join(OUT, "nifti", f"{stem2}_roi_mask.nii.gz")))
man = W.read_manifest(os.path.join(OUT, "manifest.csv"))
r2 = man.get(stem2)
check("manifest row 2: empty rect cols, mask px", r2 is not None and (r2["x0"], r2["y0"], r2["x1"], r2["y1"]) == ("", "", "", "") and int(r2["mask_pixels"]) == n2, str(r2))
check("advanced to item 3", dock._index == 2 and dock._count_lbl.text() == "3/4 · 2 done", dock._count_lbl.text())
check("all files", C.out_files(OUT) == sorted(["manifest.csv"] + [f"{f}/{stem1}_{s}{e}" for f, e in (("png", ".png"), ("jpeg", ".jpg"), ("nifti", ".nii.gz")) for s in ("image", "mask", "roi", "roi_mask")] + [f"{f}/{stem2}_{s}{e}" for f, e in (("png", ".png"), ("jpeg", ".jpg"), ("nifti", ".nii.gz")) for s in ("image", "mask")]), str(C.out_files(OUT)))
check("invariants ok end", not H.invariants(canvas), str(H.invariants(canvas)))
sys.exit(C.finish(win, app))
