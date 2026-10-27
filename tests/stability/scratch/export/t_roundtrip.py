"""Export lens, part 2: GUI save -> files -> reload through the viewer's own loader."""
import os, sys, time, shutil, warnings
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
H.register_package()
import numpy as np
from PIL import Image
import nibabel as nib
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

SCR = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/export"
WS = os.path.join(SCR, "ws_rt"); shutil.rmtree(WS, ignore_errors=True); os.makedirs(WS)
results = []
def check(name, cond, info=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""))

# ── fixtures ────────────────────────────────────────────────────────────────
CNII = "/media/zsk/ressd/research/alldata_backup/Tongyu_Wang/radiology_qingyi/qingyi/+C/2035104/C.nii"
CR   = sorted(__import__("glob").glob("/media/zsk/ressd/research/alldata_backup/dicom/original/*.dcm"))[0]
PNG  = "/media/zsk/ressd/research/alldata_backup/project_workstation/PhD/image_exsample/3.png"
shutil.copy(CNII, os.path.join(WS, "a_C.nii")); shutil.copy(CR, os.path.join(WS, "b_cr.dcm")); shutil.copy(PNG, os.path.join(WS, "c_rgba.png"))

def make_dcm(path, arr_i16, iop, spacing, intercept=-1024.0, wc=40.0, ww=400.0):
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
    ds.SOPClassUID = ds.file_meta.MediaStorageSOPClassUID; ds.SOPInstanceUID = ds.file_meta.MediaStorageSOPInstanceUID
    ds.Modality = "CT"; ds.PatientName = "SYN"; ds.PatientID = "0"; ds.StudyInstanceUID = generate_uid(); ds.SeriesInstanceUID = generate_uid()
    ds.Rows, ds.Columns = arr_i16.shape; ds.SamplesPerPixel = 1; ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16; ds.BitsStored = 16; ds.HighBit = 15; ds.PixelRepresentation = 1
    ds.RescaleIntercept = intercept; ds.RescaleSlope = 1.0; ds.WindowCenter = wc; ds.WindowWidth = ww
    ds.ImageOrientationPatient = list(iop); ds.ImagePositionPatient = [0, 0, 0]; ds.InstanceNumber = 1
    ds.PixelSpacing = list(spacing)
    ds.PixelData = np.ascontiguousarray(arr_i16, dtype=np.int16).tobytes()
    ds.save_as(path, enforce_file_format=True)

yy, xx = np.mgrid[:120, :160]
raw = (yy * 20 + xx * 5).astype(np.int16)             # gradient: top-left dark, raw 0..~3180 -> HU -1024..~2156
make_dcm(os.path.join(WS, "d_flip.dcm"), raw, (1, 0, 0, 0, -1, 0), (0.5, 0.25))   # col_dir[1] < 0 -> flip_acq_rows
make_dcm(os.path.join(WS, "e_plain.dcm"), raw, (1, 0, 0, 0, 1, 0), (0.5, 0.25))

# ── boot ────────────────────────────────────────────────────────────────────
app, win = H.boot()
dock, quad = win._dock, win._quad
ws = H.open_workspace(app, win, WS)
stems = [it.stem for it in ws.items]
check("workspace lists the 5 items", stems == ["a_C", "b_cr", "c_rgba", "d_flip", "e_plain"], str(stems))
cell = quad.active_cell(); canvas = cell.canvas()
cell2 = quad.cells()[1]
for chk in dock._fmt_chk.values(): chk.setChecked(True)
dock._image_chk.setChecked(True); dock._mask_chk.setChecked(True); dock._crop_chk.setChecked(True)
OUT = ws.out_dir

def load_item(i):
    dock._load_index(i); ok = H.wait_loaded(app, cell); H.pump(app, 100); return ok
def paint():
    dock._tool_btns["paint"].setChecked(True); dock._apply_tool(); dock._brush_spin.setValue(6); dock._apply_brush()
    H.drag(app, canvas, H.pt(canvas, 0.25, 0.3), H.pt(canvas, 0.7, 0.35))
    dock._tool_btns["rect"].setChecked(True); dock._apply_tool()
    H.drag(app, canvas, H.pt(canvas, 0.1, 0.15), H.pt(canvas, 0.8, 0.75)); H.pump(app, 50)
def save():
    seen = H.auto_close_dialogs(app, 300)
    t0 = time.time(); dock._save(advance=False); app.processEvents(); dt = time.time() - t0
    H.pump(app, 400)
    return dt, seen
def rd_png(p): return np.array(Image.open(p))
def nii(p): return nib.load(p)

def roundtrip(stem, invert):
    """Compare files against the live canvas, then reload nifti products through the loader."""
    px = canvas.displayed_pixels().copy(); m = canvas.mask().copy(); rect = canvas.crop_rect(); wc, ww = canvas.wl(); sd = cell.series_data()
    # 1. PNG image vs the canvas' own rendered buffer (what you see)
    rgb = canvas._rgb_buf[..., 0]
    im8 = rd_png(os.path.join(OUT, "png", f"{stem}_image.png"))
    d = im8.astype(int) - rgb.astype(int)
    check(f"{stem} inv={invert}: png _image == canvas render", (d == 0).all(), f"{(d!=0).sum()}/{d.size} px differ, range [{d.min()},{d.max()}]")
    # 2. PNG roi vs canvas render crop
    x0, y0, x1, y1 = rect
    roi8 = rd_png(os.path.join(OUT, "png", f"{stem}_roi.png"))
    check(f"{stem}: png _roi shape == rect", roi8.shape == (y1 - y0, x1 - x0), f"{roi8.shape} vs {(y1-y0, x1-x0)}")
    # 3. mask PNG vs canvas mask
    pm = rd_png(os.path.join(OUT, "png", f"{stem}_mask.png"))
    check(f"{stem}: png _mask == canvas mask", np.array_equal(pm > 127, m > 0), f"{int(m.sum())} px")
    # 4. NIfTI image raw == displayed pixels, spacing
    ni = nii(os.path.join(OUT, "nifti", f"{stem}_image.nii.gz")); arr = np.asarray(ni.dataobj)
    check(f"{stem}: nifti _image raw == displayed_pixels (transposed)", arr.shape == (px.shape[1], px.shape[0], 1) and np.array_equal(arr[:, :, 0].T, px), f"{arr.shape}")
    z = tuple(float(v) for v in ni.header.get_zooms()[:2])
    check(f"{stem}: nifti zooms (x=col,y=row) == (col_mm,row_mm) of panel spacing {sd.pixel_spacing}", np.allclose(z, (sd.pixel_spacing[1], sd.pixel_spacing[0])), f"zooms {z}")
    # 5. reload nifti products through LoaderWorker into panel 2
    for prod, ref in (("image", px), ("mask", m), ("roi", px[y0:y1, x0:x1]), ("roi_mask", m[y0:y1, x0:x1])):
        p = os.path.join(OUT, "nifti", f"{stem}_{prod}.nii.gz")
        ok = H.load_file(app, cell2, p); H.pump(app, 100)
        shown = cell2.canvas().displayed_pixels(); sd2 = cell2.series_data()
        same = ok and shown is not None and shown.shape == ref.shape and np.array_equal(shown, ref.astype(np.float32))
        extra = ""
        if ok and shown is not None and shown.shape == ref.shape and not same:
            extra = f"; flipud match={np.array_equal(shown, np.flipud(ref))} fliplr match={np.array_equal(shown, np.fliplr(ref))} .T match={shown.shape==ref.T.shape and np.array_equal(shown, ref.T)}"
        check(f"{stem}: reload nifti _{prod} shows the same array/orientation as drawn", same, f"loaded={ok} shape={None if shown is None else shown.shape} type={sd2.series_type if sd2 else None}{extra}")
        if prod == "image" and ok and sd2 is not None:
            check(f"{stem}: reloaded nifti pixel_spacing == original panel spacing", np.allclose(sd2.pixel_spacing, sd.pixel_spacing), f"reloaded {sd2.pixel_spacing} vs original {sd.pixel_spacing}")
    # 6. JPEG image close to PNG
    jp = rd_png(os.path.join(OUT, "jpeg", f"{stem}_image.jpg"))
    check(f"{stem}: jpeg _image within 8 grey levels of png (max abs diff)", np.abs(jp.astype(int) - im8.astype(int)).max() <= 8, f"max {np.abs(jp.astype(int) - im8.astype(int)).max()}, mean {np.abs(jp.astype(int) - im8.astype(int)).mean():.2f}")
    return px, m, rect

# ── item 0: C.nii (3-D NIfTI) ────────────────────────────────────────────────
check("item 0 (C.nii) loaded", load_item(0)); paint()
sd = cell.series_data(); z0 = cell._cur_z
print(f"INFO C.nii: type={sd.series_type} spacing={sd.pixel_spacing} slice={sd.slice_spacing} cur_z={z0} wl={canvas.wl()} shape={canvas.displayed_pixels().shape}")
dt, seen = save()
check("C.nii save ok (no dialog)", not seen and ws.items[0].done, f"{dt:.2f}s dialogs={seen}")
px0, m0, r0 = roundtrip("a_C", False)
orig = nib.load(CNII); od = np.asarray(orig.dataobj)
check("C.nii: displayed slice == original data[:, :, z].T (loader orientation)", np.array_equal(px0, od[:, :, z0].T.astype(np.float32)))
mi = nii(os.path.join(OUT, "nifti", "a_C_mask.nii.gz"))
check("C.nii: saved mask nifti data aligns index-wise with original data[:, :, z]", np.array_equal(np.asarray(mi.dataobj)[:, :, 0] > 0, (m0.T > 0)), f"mask shape {mi.shape} vs orig {orig.shape}")
check("C.nii: saved mask affine equals original affine (world alignment)", np.allclose(mi.affine[:3, :3], orig.affine[:3, :3], atol=1e-3) and np.allclose(mi.affine[:3, 3], orig.affine @ np.array([0, 0, z0, 1]), atol=1e-3)[()] if True else False,
      f"saved affine diag {np.diag(mi.affine).tolist()} origin {mi.affine[:3,3].tolist()}; original axcodes {nib.aff2axcodes(orig.affine)} z={z0}")

# ── item 1: CR DICOM (MONOCHROME1, ImagerPixelSpacing) + invert ──────────────
check("item 1 (CR) loaded", load_item(1)); paint()
win._invert_btn.setChecked(True); app.processEvents()
check("CR: invert applied on canvas", canvas.invert())
sd = cell.series_data(); print(f"INFO CR: spacing={sd.pixel_spacing} wl={canvas.wl()} shape={canvas.displayed_pixels().shape} flip_rows={sd.flip_acq_rows}")
dt, seen = save()
check("CR save ok", not seen and ws.items[1].done, f"dialogs={seen}")
check(f"CR 2044x1514 save (png+jpeg+nifti, 4 products each) blocks the GUI thread for {dt:.2f}s", dt < 3.0)
px1, m1, r1 = roundtrip("b_cr", True)
ds = pydicom.dcmread(CR); rawcr = ds.pixel_array.astype(np.float32)
check("CR: nifti raw == pydicom pixel_array (MONOCHROME1 stored verbatim, not inverted)", np.array_equal(np.asarray(nii(os.path.join(OUT,'nifti','b_cr_image.nii.gz')).dataobj)[:, :, 0].T, rawcr))
win._invert_btn.setChecked(False); app.processEvents()

# ── item 2: RGBA PNG ─────────────────────────────────────────────────────────
check("item 2 (RGBA png) loaded", load_item(2)); paint()
sd = cell.series_data(); print(f"INFO PNG: spacing={sd.pixel_spacing} wl={canvas.wl()} shape={canvas.displayed_pixels().shape}")
dt, seen = save(); check("PNG save ok", not seen and ws.items[2].done, f"dialogs={seen}")
px2, m2, r2 = roundtrip("c_rgba", False)
L = np.array(Image.open(PNG).convert("L"), np.float32)
check("PNG: displayed pixels == PIL convert('L')", np.array_equal(px2, L))

# ── item 3: flipped-IOP DICOM (flip_acq_rows) ────────────────────────────────
check("item 3 (flip dcm) loaded", load_item(3)); paint()
sd = cell.series_data(); print(f"INFO flip: flip_rows={sd.flip_acq_rows} spacing={sd.pixel_spacing} wl={canvas.wl()}")
check("flip dcm: loader flips rows (displayed == flipud(raw+intercept))", sd.flip_acq_rows and np.array_equal(canvas.displayed_pixels(), np.flipud(raw.astype(np.float32) - 1024)))
dt, seen = save(); check("flip save ok", not seen and ws.items[3].done, f"dialogs={seen}")
px3, m3, r3 = roundtrip("d_flip", False)
ni3 = np.asarray(nii(os.path.join(OUT, "nifti", "d_flip_image.nii.gz")).dataobj)[:, :, 0].T
check("flip dcm: nifti stores the DISPLAYED (flipped) orientation, i.e. != pydicom raw orientation", np.array_equal(ni3, np.flipud(raw.astype(np.float32) - 1024)) and not np.array_equal(ni3, raw.astype(np.float32) - 1024))
check("flip dcm: nifti HU values negative preserved (min)", float(ni3.min()) == -1024.0, f"min {ni3.min()} max {ni3.max()}")
# the manifest rect refers to displayed coords; check manifest row
from viewer_vidi import workspace as W
man = W.read_manifest(ws.manifest_path)
check("manifest rows for 4 items", set(man) == {"a_C", "b_cr", "c_rgba", "d_flip"}, str(sorted(man)))
check("manifest d_flip rect == canvas rect, mask_pixels == count", tuple(int(man["d_flip"][k]) for k in ("x0","y0","x1","y1")) == r3 and int(man["d_flip"]["mask_pixels"]) == int(m3.sum()), str(man["d_flip"]))

# ── item 4: plain DICOM with non-square spacing, then save with W/L changed via drag ──
check("item 4 (plain dcm) loaded", load_item(4)); paint()
dock._tool_btns["drag"].setChecked(True); dock._apply_tool()
H.drag(app, canvas, H.pt(canvas, 0.5, 0.5), H.pt(canvas, 0.8, 0.2))   # change W/L by drag
wc, ww = canvas.wl(); print(f"INFO plain: wl after drag={wc:.1f},{ww:.1f} spacing={cell.series_data().pixel_spacing}")
dt, seen = save(); check("plain save ok", not seen and ws.items[4].done, f"dialogs={seen}")
px4, m4, r4 = roundtrip("e_plain", False)
from viewer_vidi.annotation_export import window_to_uint8
check("plain: png _image == window_to_uint8(displayed, wl after drag)", np.array_equal(rd_png(os.path.join(OUT, "png", "e_plain_image.png")), window_to_uint8(px4, wc, ww)))

# ── re-export of a reloaded nifti: spacing after two trips ───────────────────
p_img = os.path.join(OUT, "nifti", "e_plain_image.nii.gz")
H.load_file(app, cell2, p_img); H.pump(app, 100)
sd2 = cell2.series_data()
from viewer_vidi.annotation_export import ExportInput, ExportOptions, export_item
d2 = os.path.join(SCR, "out", "retrip"); shutil.rmtree(d2, ignore_errors=True)
export_item(d2, ExportInput("t", cell2.canvas().displayed_pixels(), 0, 1, mask=np.ones_like(cell2.canvas().mask()), spacing=(float(sd2.pixel_spacing[0]), float(sd2.pixel_spacing[1]))), ExportOptions(formats=("nifti",), save_image=True))
z1 = tuple(float(v) for v in nii(p_img).header.get_zooms()[:2]); z2 = tuple(float(v) for v in nii(os.path.join(d2, "nifti", "t_image.nii.gz")).header.get_zooms()[:2])
check("nifti zooms stable across save -> reload -> save", np.allclose(z1, z2), f"first {z1} second {z2} (panel spacing after reload {sd2.pixel_spacing})")

win.close(); app.processEvents()
n_fail = sum(1 for _, ok in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} checks passed")
