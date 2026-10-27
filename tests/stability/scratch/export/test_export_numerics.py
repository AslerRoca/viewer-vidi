"""Export lens, part A: annotation_export.py numerics / formats (no Qt)."""
import os, sys, time, warnings, traceback
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
H.register_package()
import numpy as np
from PIL import Image
import nibabel as nib
from viewer_vidi.annotation_export import (ExportInput, ExportOptions, export_item,
                                           window_to_uint8, FORMATS)
from viewer_vidi.windowing import render_to_rgb, wl_from_percentiles, wl_from_dicom
from viewer_vidi.colormaps import COLORMAPS, COLORMAPS_INV
from viewer_vidi.gpu import GPU

SP = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/export"
OUT = os.path.join(SP, "out_numerics")
import shutil; shutil.rmtree(OUT, ignore_errors=True); os.makedirs(OUT)

results = []
def check(name, cond, info=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""), flush=True)

def run(name, fn):
    """Run fn, catching exceptions; return (ok, result_or_exc)."""
    try:
        return True, fn()
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

ALL = ExportOptions(formats=("png", "jpeg", "nifti"), save_image=True)
def rd_png(fmt, stem, suffix):
    ext = {"png": ".png", "jpeg": ".jpg"}[fmt]
    return np.array(Image.open(os.path.join(OUT, fmt, f"{stem}_{suffix}{ext}")))
def rd_nii(stem, suffix):
    return nib.load(os.path.join(OUT, "nifti", f"{stem}_{suffix}.nii.gz"))

m = np.zeros((40, 60), np.uint8); m[5:15, 10:30] = 1

# ── 1. constant image, ww=1 (wl_from_dicom floors ww at 1) ──────────────────
const = np.full((40, 60), 1234.0, np.float32)
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    ok, res = run("const", lambda: export_item(OUT, ExportInput("const", const, wc=1234, ww=1, mask=m, rect=(0, 0, 60, 40)), ALL))
check("constant image ww=1 exports without exception", ok, str(res))
if ok:
    im = rd_png("png", "const", "image")
    check("constant image at wc with ww=1 → uint8 128 everywhere", im.min() == im.max() == 128, f"min {im.min()} max {im.max()} warnings={[str(x.message) for x in w]}")
    u = window_to_uint8(const, 1234, 1)
    check("window_to_uint8 const == canvas render? (export rounds, canvas truncates)", True, f"export {u[0,0]} canvas {render_to_rgb(const, 1234, 1, COLORMAPS['Gray'])[0,0,0]}")

# ── 2. NaN / ±inf pixels ─────────────────────────────────────────────────────
bad = np.linspace(0, 100, 40 * 60, dtype=np.float32).reshape(40, 60)
bad[0, 0] = np.nan; bad[0, 1] = np.inf; bad[0, 2] = -np.inf; bad[1, 1] = np.nan
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    ok, res = run("nan", lambda: export_item(OUT, ExportInput("nan", bad, wc=50, ww=100, mask=m, rect=(0, 0, 10, 10)), ALL))
check("NaN/inf pixels export without exception", ok, str(res))
if ok:
    im = rd_png("png", "nan", "image")
    jp = rd_png("jpeg", "nan", "image")
    check("PNG: +inf→255, -inf→0", im[0, 1] == 255 and im[0, 2] == 0, f"inf→{im[0,1]} -inf→{im[0,2]}")
    print(f"  NaN pixel → PNG value {im[0,0]} / {im[1,1]}; JPEG {jp[0,0]}; numpy warnings: {[str(x.message) for x in w]}")
    check("PNG NaN pixel maps to a deterministic value (0 or 255), not garbage", im[0, 0] in (0, 255) and im[0, 0] == im[1, 1], f"{im[0,0]} {im[1,1]}")
    ni = np.asarray(rd_nii("nan", "image").dataobj)[:, :, 0].T
    check("NIfTI stores NaN and ±inf verbatim", np.isnan(ni[0, 0]) and np.isposinf(ni[0, 1]) and np.isneginf(ni[0, 2]), f"{ni[0,:3]}")
    # what would the viewer do: wl from percentiles of NaN data
    wc, ww = wl_from_percentiles(bad)
    print(f"  wl_from_percentiles on NaN data → wc={wc} ww={ww}")
    u = window_to_uint8(bad, wc, ww)
    check("all-NaN wc (percentile of NaN data) → export is NOT all one value", not (u.min() == u.max()), f"min {u.min()} max {u.max()} wc={wc}")

# ── 3. negative (HU) values with and without invert ─────────────────────────
hu = np.linspace(-1024, 3071, 40 * 60, dtype=np.float32).reshape(40, 60)
ok, res = run("hu", lambda: export_item(OUT, ExportInput("hu", hu, wc=40, ww=400, mask=m, rect=(1, 1, 59, 39)), ALL))
ok2, res2 = run("hu_inv", lambda: export_item(OUT, ExportInput("hu_inv", hu, wc=40, ww=400, invert=True, mask=m, rect=(1, 1, 59, 39)), ALL))
check("HU image exports with and without invert", ok and ok2, f"{res} {res2}")
if ok and ok2:
    a, b = rd_png("png", "hu", "image"), rd_png("png", "hu_inv", "image")
    check("invert PNG is exactly 255 - normal PNG", np.array_equal(b, 255 - a))
    check("HU window [-160,240] → below → 0, above → 255", a.flat[0] == 0 and a.flat[-1] == 255, f"{a.flat[0]} {a.flat[-1]}")
    ni = np.asarray(rd_nii("hu", "image").dataobj)[:, :, 0].T
    nii_inv = np.asarray(rd_nii("hu_inv", "image").dataobj)[:, :, 0].T
    check("NIfTI keeps negative raw values, invert ignored", np.allclose(ni, hu) and np.allclose(nii_inv, hu), f"min {ni.min()}")
    check("NIfTI image dtype float32, mask uint8", rd_nii("hu", "image").get_data_dtype() == np.float32 and rd_nii("hu", "mask").get_data_dtype() == np.uint8)

# ── 4. ww=0, ww=1e-9, negative ww ───────────────────────────────────────────
px = np.linspace(0, 100, 40 * 60, dtype=np.float32).reshape(40, 60)
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    ok, res = run("ww0", lambda: export_item(OUT, ExportInput("ww0", px, wc=50, ww=0, mask=m), ALL))
    ok2, res2 = run("wwtiny", lambda: export_item(OUT, ExportInput("wwtiny", px, wc=50, ww=1e-9, mask=m), ALL))
    ok3, res3 = run("wwneg", lambda: export_item(OUT, ExportInput("wwneg", px, wc=50, ww=-100, mask=m), ALL))
check("ww=0 / 1e-9 / -100 export without exception or warning", ok and ok2 and ok3 and not w, f"{res} {res2} {res3} warnings={[str(x.message) for x in w]}")
u0 = window_to_uint8(px, 50, 0); ut = window_to_uint8(px, 50, 1e-9); un = window_to_uint8(px, 50, -100)
check("ww=0 → binary threshold at wc", set(np.unique(u0)) <= {0, 255} and (u0 == 255).sum() > 0, f"{np.unique(u0)}")
check("ww=1e-9 → same as ww=0", np.array_equal(u0, ut))
print(f"  ww=-100 → unique {np.unique(un)[:5]} (lo = wc - ww/2 = {50 + 50}; clip(.../1e-6))")

# ── 5. wc far outside data range ─────────────────────────────────────────────
uhi = window_to_uint8(px, 1e9, 400); ulo = window_to_uint8(px, -1e9, 400)
check("wc far above → all 0; far below → all 255", uhi.max() == 0 and ulo.min() == 255, f"{uhi.max()} {ulo.min()}")
ok, res = run("wcfar", lambda: export_item(OUT, ExportInput("wcfar", px, wc=1e9, ww=400, mask=m), ALL))
check("wc far outside exports (jpeg of all-zero)", ok, str(res))

# ── 6. mask dtypes: bool, int64, float, values > 1 ───────────────────────────
for nm, mk in (("bool", m.astype(bool)), ("int64", m.astype(np.int64)), ("float", m.astype(np.float32) * 0.5),
               ("u8_255", m * 255), ("int64_256", m.astype(np.int64) * 256), ("int_neg", m.astype(np.int16) * -1)):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        ok, res = run(nm, lambda: export_item(OUT, ExportInput("mk_" + nm, px, wc=50, ww=100, mask=mk, rect=(5, 5, 35, 20)), ALL))
    if not ok:
        check(f"mask dtype {nm}: export", False, str(res)); continue
    p = rd_png("png", "mk_" + nm, "mask")
    n = np.asarray(rd_nii("mk_" + nm, "mask").dataobj)[:, :, 0].T
    png_ok = set(np.unique(p)) <= {0, 255} and (p == 255).sum() == 200
    nii_ok = set(np.unique(n)) <= {0, 1} and (n == 1).sum() == 200
    check(f"mask dtype {nm}: PNG 0/255 with 200 px", png_ok, f"unique {np.unique(p)} n255={(p==255).sum()}")
    check(f"mask dtype {nm}: NIfTI uint8 0/1 with 200 px", nii_ok, f"unique {np.unique(n)} n1={(n==1).sum()} warnings={[str(x.message) for x in w]}")

# ── 7. rect at borders / 1-px / zero-width / partly outside / negative ──────
H_, W_ = px.shape
ok, res = run("full", lambda: export_item(OUT, ExportInput("rfull", px, 50, 100, mask=m, rect=(0, 0, W_, H_)), ALL))
check("rect (0,0,w,h) exports full-size crop", ok and rd_png("png", "rfull", "roi").shape == (H_, W_), str(res))
ok, res = run("1px", lambda: export_item(OUT, ExportInput("r1px", px, 50, 100, mask=m, rect=(10, 0, 11, H_)), ALL))
check("1-px-wide rect: crop shape (H,1) in png and (1,H,1) nifti", ok and rd_png("png", "r1px", "roi").shape == (H_, 1) and rd_nii("r1px", "roi").shape == (1, H_, 1), f"{res} {rd_png('png','r1px','roi').shape if ok else ''}")
ok, res = run("1x1", lambda: export_item(OUT, ExportInput("r1x1", px, 50, 100, mask=m, rect=(10, 10, 11, 11)), ALL))
check("1x1 rect exports", ok, str(res))
ok, res = run("zero", lambda: export_item(OUT, ExportInput("rzero", px, 50, 100, mask=m, rect=(10, 10, 10, 20)), ALL))
check("zero-width rect (x0==x1): export_item raises cleanly or writes (observe)", True, f"ok={ok} {res}")
if not ok:
    print("  zero-width: written before raise:", sorted(os.listdir(os.path.join(OUT, 'png'))).count("rzero_roi.png"), [f for f in os.listdir(os.path.join(OUT, 'png')) if f.startswith('rzero')])
ok, res = run("inv", lambda: export_item(OUT, ExportInput("rinv", px, 50, 100, mask=m, rect=(30, 10, 10, 20)), ALL))
check("inverted rect (x1<x0): observe", True, f"ok={ok} {res}")
ok, res = run("out", lambda: export_item(OUT, ExportInput("rout", px, 50, 100, mask=m, rect=(40, 20, 100, 100)), ALL))
if ok:
    sh = rd_png("png", "rout", "roi").shape
    nr = rd_nii("rout", "roi")
    check("rect partly outside (40,20,100,100): crop silently clipped to (20,20)", sh == (20, 20), f"png shape {sh} nifti {nr.shape} affine origin {nr.affine[:2,3]}")
else:
    check("rect partly outside: export", False, str(res))
ok, res = run("neg", lambda: export_item(OUT, ExportInput("rneg", px, 50, 100, mask=m, rect=(-5, -5, 10, 10)), ALL))
if ok:
    sh = rd_png("png", "rneg", "roi").shape
    check("rect with negative origin (-5,-5,10,10): crop is NOT the expected 10x10", True, f"png shape {sh} (numpy negative slicing) affine origin {rd_nii('rneg','roi').affine[:2,3]}")
else:
    check("rect with negative origin: raises", True, str(res))
ok, res = run("float", lambda: export_item(OUT, ExportInput("rflt", px, 50, 100, mask=m, rect=(1.5, 2.5, 20.0, 30.0)), ALL))
check("float rect: observe", True, f"ok={ok} {res}")

# ── 8. spacing (0,0), (None,1.0), nan, negative ──────────────────────────────
for nm, sp in (("zero", (0, 0)), ("none", (None, 1.0)), ("nan", (float("nan"), 1.0)), ("neg", (-0.5, 0.5)), ("aniso", (0.5, 0.25))):
    ok, res = run("sp" + nm, lambda: export_item(OUT, ExportInput("sp_" + nm, px, 50, 100, mask=m, rect=(4, 6, 20, 30), spacing=sp), ExportOptions(formats=("nifti",), save_image=True)))
    if ok:
        ni = rd_nii("sp_" + nm, "image"); nr = rd_nii("sp_" + nm, "roi")
        z = ni.header.get_zooms()
        print(f"  spacing {nm} {sp}: zooms {tuple(round(float(v), 4) for v in z)} roi origin {nr.affine[:2,3]} sform {ni.header['sform_code']} qform {ni.header['qform_code']}")
        if nm in ("zero", "none"):
            check(f"spacing {nm} → zooms (1,1)", tuple(np.round(z[:2], 4)) == (1.0, 1.0), str(z))
        if nm == "aniso":
            check("aniso spacing (row .5, col .25) → nifti zooms (x=.25, y=.5)", tuple(np.round(z[:2], 4)) == (0.25, 0.5), str(z))
            check("aniso roi origin = (x0*col, y0*row) = (1.0, 3.0)", np.allclose(nr.affine[:2, 3], [4 * 0.25, 6 * 0.5]), str(nr.affine[:2, 3]))
        if nm == "nan":
            check("nan spacing: file written and reloadable (zooms nan?)", True, str(z))
    else:
        check(f"spacing {nm}: export", False, str(res))

# ── 9. roi_mask when mask empty inside rect but non-empty outside ──────────
ok, res = run("rm", lambda: export_item(OUT, ExportInput("rm", px, 50, 100, mask=m, rect=(40, 20, 60, 40)), ALL))
if ok:
    rmsk = rd_png("png", "rm", "roi_mask")
    check("roi_mask with empty mask inside rect: all-zero file written (observe)", True, f"written {res}; roi_mask max {rmsk.max()} shape {rmsk.shape}")
else:
    check("roi_mask empty inside rect", False, str(res))

# ── 10. stems with separators / '..' ────────────────────────────────────────
ok, res = run("sep", lambda: export_item(OUT, ExportInput("a/b", px, 50, 100, mask=m), ExportOptions(formats=("png",))))
check("stem 'a/b': observe", True, f"ok={ok} {res}")
evil_dir = os.path.join(SP, "out_numerics_evil"); shutil.rmtree(evil_dir, ignore_errors=True)
ok, res = run("dotdot", lambda: export_item(OUT, ExportInput("../../out_numerics_evil/x", px, 50, 100, mask=m), ExportOptions(formats=("png",))))
escaped = os.path.isfile(os.path.join(evil_dir, "x_mask.png"))
check("stem '../../evil/x' writes OUTSIDE out_dir (export_item has no stem sanitising)", not escaped, f"ok={ok} {res} escaped={escaped}")
ok, res = run("dotdotbare", lambda: export_item(OUT, ExportInput("..", px, 50, 100, mask=m), ExportOptions(formats=("png",))))
check("stem '..': observe", True, f"ok={ok} {res} → file {os.path.exists(os.path.join(OUT,'png','.._mask.png'))}")
ok, res = run("empty", lambda: export_item(OUT, ExportInput("", px, 50, 100, mask=m), ExportOptions(formats=("png",))))
check("empty stem writes '_mask.png' (observe)", True, f"ok={ok} {res}")
ok, res = run("space", lambda: export_item(OUT, ExportInput("a b", px, 50, 100, mask=m), ExportOptions(formats=("png",))))
check("stem with space exports", ok, str(res))
longstem = "x" * 250
ok, res = run("long", lambda: export_item(OUT, ExportInput(longstem, px, 50, 100, mask=m), ExportOptions(formats=("png", "nifti"))))
check("250-char stem: filename too long → observe", True, f"ok={ok} {str(res)[:120]}")

# ── 11. unknown format ───────────────────────────────────────────────────────
shutil.rmtree(os.path.join(OUT, "png"), ignore_errors=True)
ok, res = run("unk", lambda: export_item(OUT, ExportInput("unk", px, 50, 100, mask=m), ExportOptions(formats=("png", "bogus"))))
check("unknown format raises ValueError", not ok and res.startswith("ValueError"), str(res))
check("...but PNG products were already written before the raise (partial output)", True, f"png dir has unk files: {sorted(f for f in os.listdir(os.path.join(OUT,'png')) if f.startswith('unk')) if os.path.isdir(os.path.join(OUT,'png')) else []}")
ok, res = run("unk2", lambda: export_item(OUT, ExportInput("unk2", px, 50, 100, mask=np.zeros_like(m)), ExportOptions(formats=("bogus",))))
check("unknown format with nothing to write returns [] (no raise)", ok and res == [], str(res))
ok, res = run("case", lambda: export_item(OUT, ExportInput("case", px, 50, 100, mask=m), ExportOptions(formats=("PNG",))))
check("format 'PNG' (upper) → ValueError (observe)", not ok, str(res))

# ── 12. input dtype / contiguity: float64, int16, flipped views, Fortran ────
for nm, arr in (("f64", px.astype(np.float64)), ("i16", (px * 10).astype(np.int16)), ("flipud", np.flipud(px)), ("fliplr_T", np.fliplr(px.T.copy()).T), ("fortran", np.asfortranarray(px))):
    ok, res = run(nm, lambda: export_item(OUT, ExportInput("ct_" + nm, arr, 50, 100, mask=np.flipud(m) if nm == "flipud" else m, rect=(2, 3, 30, 20)), ALL))
    if ok:
        ni = np.asarray(rd_nii("ct_" + nm, "image").dataobj)[:, :, 0].T
        p = rd_png("png", "ct_" + nm, "image")
        check(f"input {nm}: nifti round trip equals input, png equals window_to_uint8(input)", np.allclose(ni, np.asarray(arr, np.float32)) and np.array_equal(p, window_to_uint8(arr, 50, 100)))
    else:
        check(f"input {nm}: export", False, str(res))

# ── 13. PNG mapping vs canvas render (CPU + GPU), with and without invert ──
rng = np.random.default_rng(0)
real = rng.uniform(0, 4095, (300, 400)).astype(np.float32)
for inv in (False, True):
    for wc, ww in ((2048, 4096), (1000, 1), (500.5, 333.3), (2048, 1e-6 * 0.5)):
        u = window_to_uint8(real, wc, ww, inv)
        cm = (COLORMAPS_INV if inv else COLORMAPS)["Gray"]
        cpu = render_to_rgb(real, wc, ww, cm)[..., 0]
        gpu = render_to_rgb(GPU.to_device(real), wc, ww, cm)[..., 0] if GPU.available else cpu
        d_cpu = np.abs(u.astype(int) - cpu.astype(int)); d_gpu = np.abs(u.astype(int) - gpu.astype(int))
        check(f"PNG vs canvas CPU render exact (inv={inv}, wc={wc}, ww={ww})", d_cpu.max() == 0,
              f"max diff {d_cpu.max()}, {np.count_nonzero(d_cpu)}/{d_cpu.size} px differ, mean signed (export-canvas) {np.mean(u.astype(int)-cpu.astype(int)):+.3f}")
        if GPU.available:
            check(f"PNG vs canvas GPU render exact (inv={inv}, wc={wc}, ww={ww})", d_gpu.max() == 0,
                  f"max diff {d_gpu.max()}, {np.count_nonzero(d_gpu)}/{d_gpu.size} px differ; cpu-vs-gpu max diff {np.abs(cpu.astype(int)-gpu.astype(int)).max()}")
# values exactly on quantisation boundaries
edge = np.array([[0, 1, 2, 254, 255, 255.4, 255.5, 255.6, 256, -1, 127.5, 128.49, 128.5]], np.float32)
u = window_to_uint8(edge, 127.5, 255); c = render_to_rgb(edge, 127.5, 255, COLORMAPS["Gray"])[..., 0]
print("  boundary values:", edge[0].tolist(), "\n   export:", u[0].tolist(), "\n   canvas:", c[0].tolist())
check("export of pixel == hi edge (wc+ww/2) is 255 and lo edge is 0", u[0, 4] == 255 and u[0, 0] == 0)

# ── 14. JPEG mask after lossy compression ───────────────────────────────────
# realistic blob + thin 1px line + checkerboard
mk = np.zeros((512, 512), np.uint8)
yy, xx = np.mgrid[:512, :512]
mk[(yy - 256) ** 2 + (xx - 256) ** 2 < 100 ** 2] = 1
mk[100, 50:450] = 1               # 1-px horizontal line
mk[50:450, 100] = 1               # 1-px vertical line
mk[400:460:2, 400:460:2] = 1      # checkerboard
ok, res = run("jm", lambda: export_item(OUT, ExportInput("jm", np.zeros((512, 512), np.float32), 0, 1, mask=mk), ExportOptions(formats=("jpeg", "png"), save_crop=False)))
j = rd_png("jpeg", "jm", "mask"); p = rd_png("png", "jm", "mask")
check("PNG mask lossless", np.array_equal(p, mk * 255))
nonbin = np.count_nonzero((j != 0) & (j != 255))
rethr = (j > 127).astype(np.uint8)
diff = np.count_nonzero(rethr != mk)
blob_only = np.zeros_like(mk); blob_only[(yy - 256) ** 2 + (xx - 256) ** 2 < 100 ** 2] = 1
ok, res = run("jb", lambda: export_item(OUT, ExportInput("jb", np.zeros((512, 512), np.float32), 0, 1, mask=blob_only), ExportOptions(formats=("jpeg",), save_crop=False)))
jb = rd_png("jpeg", "jb", "mask"); diff_b = np.count_nonzero((jb > 127).astype(np.uint8) != blob_only)
print(f"  JPEG q95 mask: {nonbin}/{j.size} px not 0/255 ({100*nonbin/j.size:.2f}%); after re-threshold@127 {diff} px differ from source ({100*diff/mk.sum():.2f}% of mask); blob-only: {diff_b} px differ of {blob_only.sum()}")
check("JPEG mask re-thresholded: blob-only within 0.5% of mask area", diff_b < 0.005 * blob_only.sum(), f"{diff_b}")
check("JPEG mask re-thresholded: thin lines/checkerboard — observe", True, f"{diff} px differ ({100*diff/mk.sum():.2f}%)")

# ── 15. save_mask=False with rect, mask None, etc. ──────────────────────────
ok, res = run("nm", lambda: export_item(OUT, ExportInput("nomask", px, 50, 100, mask=None, rect=(0, 0, 10, 10)), ALL))
check("mask=None + rect → image, roi only (no roi_mask)", ok and sorted(os.path.basename(r) for r in res if r.startswith("png")) == ["nomask_image.png", "nomask_roi.png"], str(res))
ok, res = run("nc", lambda: export_item(OUT, ExportInput("nocrop", px, 50, 100, mask=m, rect=(0, 0, 10, 10)), ExportOptions(formats=("png",), save_crop=False)))
check("save_crop=False with rect → mask + roi_mask (no roi)", ok and sorted(os.path.basename(r) for r in res) == ["nocrop_mask.png", "nocrop_roi_mask.png"], str(res))
ok, res = run("mm", lambda: export_item(OUT, ExportInput("mismatch", px, 50, 100, mask=np.ones((10, 10), np.uint8)), ExportOptions(formats=("png",))))
check("mask shape != pixels shape: observe (export does not validate)", True, f"ok={ok} {res}")

# ── 16. 3-D pixels (what if displayed_pixels were (H,W,3) RGB or 3-D) ───────
ok, res = run("rgb", lambda: export_item(OUT, ExportInput("rgb", np.zeros((10, 10, 3), np.float32), 50, 100, mask=np.ones((10, 10), np.uint8)), ExportOptions(formats=("png",), save_image=True)))
check("3-D pixels (H,W,3): observe", True, f"ok={ok} {res}")

# ── 17. out_dir unwritable ──────────────────────────────────────────────────
ro = os.path.join(SP, "ro_dir"); os.makedirs(ro, exist_ok=True); os.chmod(ro, 0o500)
ok, res = run("ro", lambda: export_item(ro, ExportInput("x", px, 50, 100, mask=m), ExportOptions(formats=("png",))))
os.chmod(ro, 0o700)
check("read-only out_dir raises PermissionError (dock shows 'Export failed')", not ok and "Permission" in res, str(res))

# ── 18. out_dir is a file ───────────────────────────────────────────────────
fpath = os.path.join(SP, "a_file"); open(fpath, "w").close()
ok, res = run("odf", lambda: export_item(fpath, ExportInput("x", px, 50, 100, mask=m), ExportOptions(formats=("png",))))
check("out_dir is an existing file → raises (observe)", not ok, str(res))

n_fail = sum(1 for _, ok in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} checks passed")
