"""MONOCHROME1 handling and VOI-LUT windows: the flip and the default window at load, and the two
tools that bring earlier exports up to date (no GUI)."""
import os, sys, csv, glob, hashlib, shutil, tempfile, types, importlib.util
os.environ["QT_QPA_PLATFORM"] = "offscreen"
SP = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(os.path.dirname(SP))

pkg = types.ModuleType("viewer_vidi"); pkg.__path__ = [SRC]; pkg.__package__ = "viewer_vidi"
pkg.__file__ = os.path.join(SRC, "__init__.py"); sys.modules["viewer_vidi"] = pkg
spec = importlib.util.spec_from_file_location("viewer_vidi", pkg.__file__); spec.loader.exec_module(pkg)

import numpy as np
import nibabel as nib
import pydicom
from pydicom.dataset import Dataset
from PyQt5.QtCore import QCoreApplication

from viewer_vidi import workspace as W
from viewer_vidi.annotation_export import ExportInput, ExportOptions, export_item
from viewer_vidi.loader import LoaderWorker
from viewer_vidi.windowing import apply_rescale, mono1_flip_sum, wl_from_dicom, wl_from_percentiles

rspec = importlib.util.spec_from_file_location("repair_mono1", os.path.join(SRC, "tools", "repair_mono1.py"))
R = importlib.util.module_from_spec(rspec); rspec.loader.exec_module(R)
uspec = importlib.util.spec_from_file_location("update_exports", os.path.join(SRC, "tools", "update_exports.py"))
U = importlib.util.module_from_spec(uspec); uspec.loader.exec_module(U)

results = []
def check(name, cond, info=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""))

# ── 1. the flip itself ───────────────────────────────────────────────────────
def hdr(photometric, bits=12, signed=0, **tags):
    ds = Dataset()
    ds.PhotometricInterpretation = photometric
    ds.BitsStored, ds.PixelRepresentation = bits, signed
    for k, v in tags.items():
        setattr(ds, k, v)
    return ds
check("flip constant comes from the header: 12 bit unsigned 4095, 16 bit signed −1, rescale applied, none for MONOCHROME2",
      mono1_flip_sum(hdr("MONOCHROME1")) == 4095 and mono1_flip_sum(hdr("MONOCHROME1", 16, 1)) == -1
      and mono1_flip_sum(hdr("MONOCHROME1", RescaleSlope=2, RescaleIntercept=-100)) == 2 * 4095 - 200
      and mono1_flip_sum(hdr("MONOCHROME2")) is None and mono1_flip_sum(hdr("RGB")) is None)
raw = np.array([[0, 100], [4000, 4095]], np.uint16)
check("values of a MONOCHROME1 film are flipped, others only rescaled",
      np.array_equal(apply_rescale(raw, hdr("MONOCHROME1")), 4095.0 - raw)
      and np.array_equal(apply_rescale(raw, hdr("MONOCHROME2")), raw.astype(np.float32))
      and np.array_equal(apply_rescale(raw, hdr("MONOCHROME1", RescaleSlope=2, RescaleIntercept=-100)),
                         (2 * 4095 - 200) - (2.0 * raw - 100)))
check("a header window is mirrored with the values, its width kept",
      wl_from_dicom(hdr("MONOCHROME1", WindowCenter=1000, WindowWidth=500)) == (3095.0, 500.0)
      and wl_from_dicom(hdr("MONOCHROME2", WindowCenter=1000, WindowWidth=500)) == (1000.0, 500.0)
      and wl_from_dicom(hdr("MONOCHROME1")) == (None, None))

def with_lut(ds, entries, first):
    item = Dataset(); item.LUTDescriptor = [entries, first, 16]
    ds.VOILUTSequence = [item]
    return ds
check("without a window in the header, the range of the VOI LUT is the default window (mirrored for MONOCHROME1)",
      wl_from_dicom(with_lut(hdr("MONOCHROME2"), 1250, 1918)) == (2542.5, 1250.0)
      and wl_from_dicom(with_lut(hdr("MONOCHROME1"), 1250, 1918)) == (4095 - 2542.5, 1250.0)
      and wl_from_dicom(with_lut(hdr("MONOCHROME2", 16), 0, 0)) == (32767.5, 65536.0)
      and wl_from_dicom(with_lut(hdr("MONOCHROME2", WindowCenter=1000, WindowWidth=500), 1250, 1918)) == (1000.0, 500.0))

# ── 2. the loader, on a fixture film and its MONOCHROME2 twin ─────────────────
app = QCoreApplication(sys.argv)
fixtures = sorted(glob.glob(os.path.join(SP, "ws_img", "*.dcm")))
tmp = tempfile.mkdtemp(prefix="vidi_mono1_")
ws = os.path.join(tmp, "ws"); os.makedirs(os.path.join(ws, "sub"))
film_a, film_b, film_c = os.path.join(ws, "a.dcm"), os.path.join(ws, "sub", "b.dcm"), os.path.join(ws, "c.dcm")
shutil.copy(fixtures[0], film_a); shutil.copy(fixtures[1], film_b)
ds = pydicom.dcmread(film_a)
stored = ds.pixel_array
rows, cols = stored.shape
twin = pydicom.dcmread(film_a)
twin.PixelData = (4095 - stored).astype(stored.dtype).tobytes()
twin.PhotometricInterpretation = "MONOCHROME2"
twin.WindowCenter, twin.WindowWidth = 2000, 3000          # unlike the fixture, a film with its own window
twin.save_as(film_c)

worker = LoaderWorker()
loaded_a = worker._read_slice(film_a, rows, cols, strict=True)
loaded_c = worker._read_slice(film_c, rows, cols, strict=True)
check("the fixture is a MONOCHROME1 film and loads flipped", ds.PhotometricInterpretation == "MONOCHROME1"
      and np.array_equal(loaded_a, 4095.0 - stored))
check("its MONOCHROME2 twin loads to the identical picture", np.array_equal(loaded_a, loaded_c))

# ── 3. repair of an output directory written before the fix ──────────────────
# Products as the old viewer wrote them: NIfTI = stored values; 8-bit = the screen,
# i.e. the stored values windowed, inverted only where the user had pressed Invert.
out = os.path.join(ws, "vidi_output")
mask = np.zeros(stored.shape, np.uint8); mask[300:500, 200:600] = 1
rect = (100, 150, 900, 1250)
stored_b = pydicom.dcmread(film_b).pixel_array
old_fields = ("stem", "source", "status", "saved_at", "view", "mask_pixels", "x0", "y0", "x1", "y1", "formats", "files", "note")
old_rows = []
for stem, src, px, inverted in (("a", "a.dcm", stored, True), ("b", "sub/b.dcm", stored_b, False),
                                ("c", "c.dcm", 4095 - stored, False)):
    pixels = px.astype(np.float32)
    wc, ww = wl_from_percentiles(pixels)
    files = export_item(out, ExportInput(stem=stem, pixels=pixels, wc=wc, ww=ww, invert=inverted, mask=mask, rect=rect),
                        ExportOptions(formats=("png", "nifti"), save_image=True))
    for f in [f for f in files if "_rect_mask" in f]:       # a product the old viewer did not write
        os.remove(os.path.join(out, f)); files.remove(f)
    old_rows.append(dict(stem=stem, source=src, status="saved", saved_at="2026-11-01T10:00:00", view="",
                         mask_pixels=int(mask.sum()), x0=rect[0], y0=rect[1], x1=rect[2], y1=rect[3],
                         formats="png nifti", files=";".join(files), note="keep me"))
old_rows.append(dict(stem="d", source="gone.dcm", status="saved", files="nifti/d_image.nii.gz"))
old_rows.append(dict(stem="e", source="a.dcm", status="deleted"))
manifest = os.path.join(out, "manifest.csv")
with open(manifest, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=old_fields); w.writeheader(); w.writerows(old_rows)

def digests():
    return {os.path.relpath(p, out): hashlib.md5(open(p, "rb").read()).hexdigest()
            for p in glob.glob(os.path.join(out, "**", "*"), recursive=True) if os.path.isfile(p)}
def values(rel):
    return np.asarray(nib.load(os.path.join(out, rel)).dataobj)[:, :, 0].T
quiet = lambda _line: None

before = digests()
n = R.repair(out, apply=False, out=quiet)
check("dry run counts what it would do and writes nothing",
      n["MONOCHROME1 films"] == 2 and n["NIfTI to rewrite"] == 4 and n["not MONOCHROME1 — nothing to change"] == 1
      and n["source not found — left alone"] == 1 and n["not saved (deleted mark)"] == 1 and digests() == before, str(dict(n)))
check("8-bit products are checked against the film: saved with Invert = right, without = negative",
      n["8-bit products: right"] == 2 and n["8-bit products: negative"] == 2 and n["8-bit products: unclear"] == 0, str(dict(n)))

n = R.repair(out, apply=True, out=quiet)
after = digests()
changed = sorted(k for k in after if after[k] != before.get(k))
x0, y0, x1, y1 = rect
check("apply rewrites exactly the NIfTI image and crop of the MONOCHROME1 films, and the manifest",
      changed == ["manifest.csv", "nifti/a_image.nii.gz", "nifti/a_roi.nii.gz", "nifti/b_image.nii.gz", "nifti/b_roi.nii.gz"]
      and n["NIfTI rewritten"] == 4, str(changed))
roi = nib.load(os.path.join(out, "nifti", "a_roi.nii.gz"))
check("the rewritten values are what the viewer now loads, the crop keeps its place",
      np.array_equal(values("nifti/a_image.nii.gz"), loaded_a)
      and np.array_equal(values("nifti/a_roi.nii.gz"), loaded_a[y0:y1, x0:x1])
      and np.array_equal(values("nifti/b_roi.nii.gz"), 4095.0 - stored_b[y0:y1, x0:x1])
      and np.allclose(roi.affine[:2, 3], [x0, y0]) and roi.header.get_xyzt_units()[0] == "mm", str(roi.affine[:2, 3]))
man = W.read_manifest(manifest)
check("rows are marked with the film's polarity; other columns and rows stay",
      [man[s]["photometric"] for s in "abc"] == ["MONOCHROME1", "MONOCHROME1", "MONOCHROME2"]
      and man["a"]["note"] == "keep me" and man["a"]["x1"] == "900" and man["d"]["photometric"] == ""
      and man["e"]["status"] == "deleted" and len(man) == 5, str({s: man[s].get("photometric") for s in man}))

n = R.repair(out, apply=True, out=quiet)
check("a second run changes nothing", digests() == after and n["already in the new convention"] == 3
      and n["NIfTI rewritten"] == 0 and n["MONOCHROME1 films"] == 0, str(dict(n)))
W.write_manifest_row(manifest, {**man["a"], "photometric": ""})     # as if a run had died before marking the row
marked = digests()
n = R.repair(out, apply=True, out=quiet)
now = digests()
check("a file that was already rewritten is never flipped twice",
      n["NIfTI already rewritten"] == 2 and n["NIfTI rewritten"] == 0
      and all(now[k] == marked[k] for k in now if k != "manifest.csv")
      and W.read_manifest(manifest)["a"]["photometric"] == "MONOCHROME1", str(dict(n)))
check("command line: the workspace above the output dir is accepted, a folder without manifest refused",
      R.main([ws]) == 0 and R.main([tmp]) == 2)

# ── 4. the other tool: uniform default window for the 8-bit products, rectangle masks ──
from viewer_vidi.annotation_export import window_to_uint8
from PIL import Image
def png(rel):
    return np.array(Image.open(os.path.join(out, rel)))
before = digests()
n = U.update(out, default_window=True, rect_masks=True, apply=False, out=quiet)
check("dry run of the update counts and writes nothing",
      n["window: LUT films to render again"] == 2 and n["window: PNG / JPEG files to replace"] == 4
      and n["window: film has its own header window (or no LUT) — left alone"] == 1
      and n["masks: rows to get one"] == 3 and n["masks: files to write"] == 6 and digests() == before, str(dict(n)))

n = U.update(out, default_window=True, rect_masks=False, apply=True, out=quiet)
after = digests()
kept = sorted(k for k in after if k.startswith("replaced-"))
changed = sorted(k for k in after if k in before and after[k] != before[k])
wc_a, ww_a = wl_from_dicom(ds)
check("the PNG image and crop of the films without a header window are rendered again, the old ones kept aside",
      changed == ["manifest.csv", "png/a_image.png", "png/a_roi.png", "png/b_image.png", "png/b_roi.png"]
      and [os.path.join(*k.split(os.sep)[1:]) for k in kept] == ["png/a_image.png", "png/a_roi.png", "png/b_image.png", "png/b_roi.png"]
      and all(after[k] == before[os.path.join(*k.split(os.sep)[1:])] for k in kept), f"{changed} {kept}")
check("they now show the default window of today's viewer, not inverted",
      np.array_equal(png("png/a_image.png"), window_to_uint8(loaded_a, wc_a, ww_a))
      and np.array_equal(png("png/a_roi.png"), window_to_uint8(loaded_a[y0:y1, x0:x1], wc_a, ww_a))
      and (wc_a, ww_a) != wl_from_percentiles(loaded_a))
man = W.read_manifest(manifest)
check("their rows record that window; the film with its own window is left as it was",
      all(man[s]["wl_default"] == "1" and man[s]["invert"] == "0" for s in "ab")
      and (float(man["a"]["wc"]), float(man["a"]["ww"])) == (wc_a, ww_a)
      and (float(man["b"]["wc"]), float(man["b"]["ww"])) == wl_from_dicom(pydicom.dcmread(film_b, stop_before_pixels=True))
      and man["c"].get("wl_default", "") == "" and man["a"]["note"] == "keep me",
      str({s: (man[s].get("wc"), man[s].get("ww"), man[s].get("wl_default")) for s in "abc"}))

n = U.update(out, default_window=True, rect_masks=True, apply=True, out=quiet)
masked = digests()
new = sorted(k for k in masked if k not in after)
man = W.read_manifest(manifest)
box, area = png("png/a_rect_mask.png"), (x1 - x0) * (y1 - y0)
nbox, nimg = (nib.load(os.path.join(out, "nifti", f"a_{s}.nii.gz")) for s in ("rect_mask", "image"))
check("every row with a rectangle gets its rectangle mask in each of its formats; nothing else changes",
      new == sorted(f"{fmt}/{s}_rect_mask{ext}" for fmt, ext in (("png", ".png"), ("nifti", ".nii.gz")) for s in "abc")
      and all(masked[k] == after[k] for k in after if k != "manifest.csv")
      and n["window: already the default"] == 2 and n["masks: files written"] == 6, f"{new} {dict(n)}")
check("the mask lies on the whole image: the rectangle is 1, the geometry is the image's, the manifest lists it",
      box.shape == stored.shape and int((box == 255).sum()) == area and (box[y0:y1, x0:x1] == 255).all()
      and nbox.shape == nimg.shape and np.array_equal(nbox.affine, nimg.affine) and int(np.asarray(nbox.dataobj).sum()) == area
      and man["a"]["files"].split(";")[-2:] == ["png/a_rect_mask.png", "nifti/a_rect_mask.nii.gz"]
      and "rect_mask" not in man["d"]["files"], man["a"]["files"])
n = U.update(out, default_window=True, rect_masks=True, apply=True, out=quiet)
check("a second run of the update changes nothing", digests() == masked and n["masks: already there"] == 3
      and n["window: already the default"] == 2, str(dict(n)))
n = R.repair(out, apply=False, out=quiet)
check("the repair of the NIfTI values is not disturbed by the new files",
      n["already in the new convention"] == 3 and n["MONOCHROME1 films"] == 0, str(dict(n)))

shutil.rmtree(tmp, ignore_errors=True)
n_fail = sum(1 for _, ok in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} checks passed")
sys.exit(1 if n_fail else 0)
