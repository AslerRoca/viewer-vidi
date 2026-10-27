"""loaderasync T3: per-format items through the job flow — 3-D NIfTI, 2-D NIfTI (anisotropic),
RGBA PNG, 16-bit PNG, LA PNG, multi-frame DICOM, MONOCHROME1/2, extensionless DICOM, list→dir."""
import os, sys, time, shutil
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
import numpy as np
import nibabel as nib
from PIL import Image

FX = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/loaderasync/fx"
results = []
def check(name, cond, info=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""), flush=True)

app, win = H.boot()
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
errors = []
cell._loader.load_error.connect(lambda s: errors.append(s))
from viewer_vidi.windowing import render_to_rgb
def screen():
    """gray channel of the canvas's actual on-screen RGB buffer"""
    return canvas._rgb_buf[..., 0].copy()
from viewer_vidi.annotation_export import window_to_uint8

root = os.path.join(FX, "formats")
outd = os.path.join(root, "vidi_output")
shutil.rmtree(outd, ignore_errors=True)
ws = H.open_workspace(app, win, root)
stems = [it.stem for it in ws.items]
print("INFO items:", stems)
for c in dock._fmt_chk.values(): c.setChecked(True)
dock._image_chk.setChecked(True); dock._mask_chk.setChecked(True); dock._crop_chk.setChecked(True)

def go(stem, timeout=20):
    errors.clear()
    dock._load_index(stems.index(stem))
    ok = H.wait_loaded(app, cell, timeout)
    t0 = time.time()
    while cell._loader.isRunning() and time.time() - t0 < 10: app.processEvents(); time.sleep(0.01)
    H.pump(app, 150)
    return ok

def paint_and_save(stem):
    """paint a brush dot in the middle + rect over the centre quarter; save all formats."""
    dock._tool_btns["paint"].setChecked(True); dock._apply_tool()
    H.drag(app, canvas, H.pt(canvas, 0.45, 0.5), H.pt(canvas, 0.55, 0.5))
    dock._tool_btns["rect"].setChecked(True); dock._apply_tool()
    H.drag(app, canvas, H.pt(canvas, 0.25, 0.25), H.pt(canvas, 0.75, 0.75))
    seen = H.auto_close_dialogs(app, 150)
    dock._save(advance=False); H.pump(app, 300)
    return dock._status_lbl.text(), seen

def saved(stem, suffix, fmt):
    ext = {"png": ".png", "jpeg": ".jpg", "nifti": ".nii.gz"}[fmt]
    p = os.path.join(outd, fmt, f"{stem}_{suffix}{ext}")
    if not os.path.isfile(p): return None
    if fmt == "nifti": return nib.load(p)
    return np.array(Image.open(p))

# ── 3-D NIfTI (C.nii 384x288x56) ─────────────────────────────────────────────
ok = go("c3d")
sd = cell.series_data(); px = canvas.displayed_pixels()
check("N3.1 3-D NIfTI item loads", ok and sd is not None, str(errors))
check("N3.2 displayed slice is (Y, X) = (288, 384), aspect 1", px.shape == (288, 384) and canvas._aspect == 1.0, f"{px.shape} asp={canvas._aspect}")
check("N3.3 initial slice is the middle one (z=28 of 56)", cell._cur_z == 28, f"cur_z={cell._cur_z}")
src = nib.load(os.path.join(root, "c3d.nii"))
vol = np.asarray(src.dataobj, dtype=np.float32)
check("N3.4 displayed pixels == source[:, :, 28].T", np.array_equal(px, vol[:, :, 28].T))
check("N3.5 sd.pixel_spacing from zooms", tuple(np.round(sd.pixel_spacing, 4)) == (1.1328, 1.1328) and round(sd.slice_spacing, 3) == 4.0, f"{sd.pixel_spacing} {sd.slice_spacing}")
scr = screen()
st, seen = paint_and_save("c3d")
m = canvas.mask(); r = canvas.crop_rect()
png_m = saved("c3d", "mask", "png"); png_i = saved("c3d", "image", "png"); png_roi = saved("c3d", "roi", "png")
ni_i = saved("c3d", "image", "nifti"); ni_m = saved("c3d", "mask", "nifti"); ni_roi = saved("c3d", "roi", "nifti")
check("N3.6 saved PNG mask/image have the displayed slice shape", png_m is not None and png_m.shape == m.shape == px.shape, f"{None if png_m is None else png_m.shape} vs {m.shape}")
check("N3.7 saved nifti image is (X,Y,1)=(384,288,1) and equals the displayed slice", ni_i is not None and ni_i.shape == (384, 288, 1) and np.array_equal(np.asarray(ni_i.dataobj)[:, :, 0].T, px), f"{None if ni_i is None else ni_i.shape}")
check("N3.8 saved nifti image equals source slice 28 raw values", ni_i is not None and np.array_equal(np.asarray(ni_i.dataobj)[:, :, 0], vol[:, :, 28]))
check("N3.9 saved nifti zooms (1.1328, 1.1328, 1)", ni_i is not None and tuple(np.round(ni_i.header.get_zooms(), 4)) == (1.1328, 1.1328, 1.0), str(None if ni_i is None else ni_i.header.get_zooms()))
check("N3.10 roi shapes match rect", r is not None and png_roi.shape == (r[3]-r[1], r[2]-r[0]) and ni_roi.shape == (r[2]-r[0], r[3]-r[1], 1), f"rect={r} png_roi={png_roi.shape} ni_roi={ni_roi.shape}")
check("N3.11 saved PNG image == on-screen render (±1 LSB)", png_i is not None and np.abs(png_i.astype(int) - scr.astype(int)).max() <= 1,
      f"maxdiff={None if png_i is None else np.abs(png_i.astype(int) - scr.astype(int)).max()}")
check("N3.11b saved PNG image == on-screen render EXACTLY", png_i is not None and np.array_equal(png_i, scr),
      f"n_diff={None if png_i is None else int((png_i != scr).sum())}")
# change slice after painting: mask persists (documented) — save then writes slice z+5 with the same mask
cell._slice_slider.setValue(33); H.pump(app, 100)
px2 = canvas.displayed_pixels()
check("N3.12 slice change keeps mask (documented 2-D limitation) and displayed slice changes", canvas.mask_pixels() > 0 and not np.array_equal(px, px2))
dock._save(advance=False); H.pump(app, 200)
ni_i2 = saved("c3d", "image", "nifti")
check("N3.13 re-save after slice change overwrites with the new slice (33)", np.array_equal(np.asarray(ni_i2.dataobj)[:, :, 0], vol[:, :, 33]))

# ── 2-D NIfTI anisotropic: X=40, Y=30, zooms (0.5, 2.0) ─────────────────────
ok = go("n2d_aniso")
sd = cell.series_data(); px = canvas.displayed_pixels()
src2 = nib.load(os.path.join(root, "n2d_aniso.nii.gz")); a2 = np.asarray(src2.dataobj, dtype=np.float32)
print("INFO n2d: displayed shape", px.shape, "spacing", sd.pixel_spacing, "aspect", canvas._aspect)
check("N2.1 2-D NIfTI loads", ok and sd is not None, str(errors))
check("N2.2 2-D NIfTI displayed as (Y, X) = (30, 40) like the 3-D convention", px.shape == (30, 40), f"shape={px.shape} (3-D convention would give (Y,X)=(30,40); got rows=X if (40,30))")
rows_are_x = px.shape == (40, 30)
# whichever orientation: does the spacing attached to the displayed rows/cols match?
row_mm_expected = 2.0 if px.shape == (30, 40) else 0.5     # rows=Y → 2.0 ; rows=X → 0.5
col_mm_expected = 0.5 if px.shape == (30, 40) else 2.0
check("N2.3 sd.pixel_spacing (row, col) matches the displayed axes", tuple(sd.pixel_spacing) == (row_mm_expected, col_mm_expected), f"sd.pixel_spacing={sd.pixel_spacing} expected (row,col)=({row_mm_expected},{col_mm_expected})")
st, seen = paint_and_save("n2d_aniso")
ni = saved("n2d_aniso", "image", "nifti")
check("N2.4 2-D nifti export written", ni is not None, st)
if ni is not None:
    print("INFO n2d export shape", ni.shape, "zooms", ni.header.get_zooms(), "source zooms", src2.header.get_zooms())
    check("N2.5 exported nifti has the SOURCE axis order (X=40, Y=30) and zooms (0.5, 2.0)", ni.shape[:2] == (40, 30) and tuple(np.round(ni.header.get_zooms()[:2], 3)) == (0.5, 2.0), f"{ni.shape} {ni.header.get_zooms()}")
    check("N2.6 exported nifti voxel values equal source (same [x,y] indexing)", ni.shape[:2] == a2.shape and np.array_equal(np.asarray(ni.dataobj)[:, :, 0], a2))

# ── 3-D NIfTI anisotropic: X=40, Y=30, Z=5, zooms (0.5, 2.0, 3.0) ───────────
ok = go("n3d_aniso")
sd = cell.series_data(); px = canvas.displayed_pixels()
print("INFO n3d: displayed shape", px.shape, "spacing", sd.pixel_spacing, "slice", sd.slice_spacing)
check("N3A.1 3-D aniso displayed (Y, X)=(30, 40)", px.shape == (30, 40), str(px.shape))
check("N3A.2 sd.pixel_spacing is (row=Y 2.0, col=X 0.5)", tuple(sd.pixel_spacing) == (2.0, 0.5), f"sd.pixel_spacing={sd.pixel_spacing}")
st, seen = paint_and_save("n3d_aniso")
ni = saved("n3d_aniso", "image", "nifti")
if ni is not None:
    print("INFO n3d export shape", ni.shape, "zooms", ni.header.get_zooms())
    check("N3A.3 exported nifti zooms are (X 0.5, Y 2.0) like the source", tuple(np.round(ni.header.get_zooms()[:2], 3)) == (0.5, 2.0), f"{ni.header.get_zooms()}")

# ── RGBA PNG 296x252 ─────────────────────────────────────────────────────────
ok = go("rgba")
px = canvas.displayed_pixels()
check("R.1 RGBA PNG loads as (252, 296) grey", ok and px is not None and px.shape == (252, 296), f"{None if px is None else px.shape} {errors}")
st, seen = paint_and_save("rgba")
im = saved("rgba", "image", "png"); mk = saved("rgba", "mask", "png")
check("R.2 RGBA export shapes", im is not None and im.shape == (252, 296) and mk.shape == (252, 296), st)
ref = np.array(Image.open(os.path.join(root, "rgba.png")).convert("L")).astype(np.float32)
check("R.3 displayed pixels == PIL convert('L')", np.array_equal(px, ref))

# ── 16-bit PNG ───────────────────────────────────────────────────────────────
ok = go("p16")
px = canvas.displayed_pixels(); sd = cell.series_data()
check("P16.1 16-bit PNG loads with full range", ok and px is not None and px.shape == (48, 64) and px.max() == 60000, f"{None if px is None else (px.shape, px.min(), px.max())} {errors}")
st, seen = paint_and_save("p16")
im = saved("p16", "image", "png"); ni = saved("p16", "image", "nifti")
check("P16.2 16-bit export: png written with W/L applied and nifti keeps raw", im is not None and im.max() == 255 and im.min() == 0 and ni is not None and float(np.asarray(ni.dataobj).max()) == 60000.0, st)

# ── LA PNG ───────────────────────────────────────────────────────────────────
ok = go("la", timeout=6)
px = canvas.displayed_pixels()
print("INFO la.png: loaded", ok, "errors", errors, "px", None if px is None else px.shape)
check("LA.1 grey+alpha PNG loads (or at least reports an error visibly)", ok, f"errors={errors}")
if ok:
    st, seen = paint_and_save("la")
    check("LA.2 export written", saved("la", "image", "png") is not None, st)

# ── multi-frame DICOM (3 frames 50x60) ───────────────────────────────────────
ok = go("multiframe")
px = canvas.displayed_pixels(); sd = cell.series_data()
print("INFO multiframe: loaded", ok, "errors", errors, "px", None if px is None else (px.shape, float(px.min()), float(px.max())), "type", sd.series_type if sd else None, "n_t", sd.n_timepoints if sd else None)
check("MF.1 multi-frame DICOM shows real pixel values (not all zero)", ok and px is not None and px.max() > 0, f"px={None if px is None else (px.shape, float(px.min()), float(px.max()))}")
st, seen = paint_and_save("multiframe")
im = saved("multiframe", "image", "png"); ni = saved("multiframe", "image", "nifti")
check("MF.2 multi-frame export is not a silent all-zero image", ni is None or float(np.asarray(ni.dataobj).max()) > 0, f"status={st} nifti_max={None if ni is None else float(np.asarray(ni.dataobj).max())}")

# ── MONOCHROME1 vs MONOCHROME2 (identical PixelData) ─────────────────────────
ok = go("mono1"); px1 = canvas.displayed_pixels().copy(); wl1 = canvas.wl(); inv1 = canvas.invert()
rgb1 = screen()
st, seen = paint_and_save("mono1"); im1 = saved("mono1", "image", "png")
ok = go("mono2"); px2 = canvas.displayed_pixels().copy(); wl2 = canvas.wl(); inv2 = canvas.invert()
rgb2 = screen()
st, seen = paint_and_save("mono2"); im2 = saved("mono2", "image", "png")
print("INFO mono1 display corner (0,0)/(−1,−1):", rgb1[0, 0], rgb1[-1, -1], "export:", im1[0, 0], im1[-1, -1], "| mono2:", rgb2[0, 0], rgb2[-1, -1], "export:", im2[0, 0], im2[-1, -1], "invert flags", inv1, inv2)
check("M.1 MONOCHROME1 export matches its own display (±1)", np.abs(im1.astype(int) - rgb1.astype(int)).max() <= 1, f"maxdiff={np.abs(im1.astype(int) - rgb1.astype(int)).max()}")
check("M.2 MONOCHROME2 export matches its own display (±1)", np.abs(im2.astype(int) - rgb2.astype(int)).max() <= 1)
check("M.3 MONOCHROME1 is displayed inverted relative to MONOCHROME2 (DICOM semantics)", rgb1[0, 0] > rgb1[-1, -1] and rgb2[0, 0] < rgb2[-1, -1], f"mono1 (0,0)={rgb1[0,0]} (-1,-1)={rgb1[-1,-1]}; mono2 (0,0)={rgb2[0,0]} (-1,-1)={rgb2[-1,-1]}")
# with the toolbar Invert toggled on: export follows
win._invert_btn.setChecked(True); H.pump(app, 100)
inv_now = canvas.invert()
dock._save(advance=False); H.pump(app, 200)
im2i = saved("mono2", "image", "png")
check("M.4 toolbar Invert is applied to the export", inv_now and np.abs(im2i.astype(int) - (255 - rgb2.astype(int))).max() <= 1, f"invert={inv_now} maxdiff={np.abs(im2i.astype(int) - (255 - rgb2.astype(int))).max()}")
win._invert_btn.setChecked(False); H.pump(app, 100)

# ── extensionless DICOM items (image mode) ───────────────────────────────────
root_e = os.path.join(FX, "extless")
shutil.rmtree(os.path.join(root_e, "vidi_output"), ignore_errors=True)
ws_e = H.open_workspace(app, win, root_e)
check("X.1 extensionless DICOM dir: 20 items, one per file", len(ws_e.items) == 20, str(len(ws_e.items)))
ok = H.wait_loaded(app, cell)
sd = cell.series_data(); px = canvas.displayed_pixels()
check("X.2 extensionless item loads as 2-D 200x200", ok and px is not None and px.shape == (200, 200) and sd.series_type.name == "S2D", f"{None if px is None else px.shape} {sd.series_type if sd else None}")
check("X.3 pixel spacing from DICOM (2, 2)", tuple(sd.pixel_spacing) == (2.0, 2.0), str(sd.pixel_spacing))
for c in dock._fmt_chk.values(): c.setChecked(True)
dock._image_chk.setChecked(True)
st, seen = paint_and_save(ws_e.items[0].stem)
outd_e = os.path.join(root_e, "vidi_output")
check("X.4 extensionless item saves with numeric stem", os.path.isfile(os.path.join(outd_e, "png", f"{ws_e.items[0].stem}_image.png")), f"{st} stem={ws_e.items[0].stem}")
# reopen: done flag honoured for numeric stems
ws_e2 = H.open_workspace(app, win, root_e)
check("X.5 reopen marks numeric-stem item done and jumps to item 1", ws_e2.items[0].done and dock._index == 1)

# ── list workspace whose entry is a DICOM series directory ───────────────────
root_l = os.path.join(FX, "listdir")
from viewer_vidi import workspace as W
lf = os.path.join(root_l, "items.txt")
paths = W.parse_list_file(lf)
ws_l = W.build_workspace(root_l, "list", paths, list_file=lf)
print("INFO listdir: parsed", len(paths), "items", [it.stem for it in ws_l.items], "missing", ws_l.missing)
check("L.1 list entry pointing at a DICOM series directory is NOT silently dropped as 'not found'",
      not any(os.path.isdir(m) for m in ws_l.missing), f"missing={ws_l.missing}")
dock._set_workspace(ws_l); ok = H.wait_loaded(app, cell)
check("L.2 list: extensionless file entry loads", ok and dock._index == 0, str(dock._status_lbl.text()))

win.close(); app.processEvents()
nf = sum(1 for _, ok in results if not ok)
print(f"\n{len(results) - nf}/{len(results)} checks passed")
