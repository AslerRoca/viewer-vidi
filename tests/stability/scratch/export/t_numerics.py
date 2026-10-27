"""Export lens, part 1: annotation_export.py numerics / formats (no Qt)."""
import os, sys, time, warnings, shutil, traceback
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
H.register_package()
import numpy as np
from PIL import Image
import nibabel as nib
from viewer_vidi.annotation_export import ExportInput, ExportOptions, export_item, window_to_uint8, FORMATS
from viewer_vidi.windowing import render_to_rgb, wl_from_percentiles
from viewer_vidi.colormaps import COLORMAPS, COLORMAPS_INV
from viewer_vidi import workspace as W

OUT = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/export/out"
results = []
def check(name, cond, info=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""))
def fresh(name):
    d = os.path.join(OUT, name); shutil.rmtree(d, ignore_errors=True); os.makedirs(d); return d
def rd_png(p): return np.array(Image.open(p))
def rd_nii(p): return np.asarray(nib.load(p).dataobj)
ALL = ExportOptions(formats=("png", "jpeg", "nifti"), save_image=True)

# ── A. window_to_uint8 vs canvas render (CPU) ────────────────────────────────
ramp = np.linspace(-100, 4200, 512 * 512, dtype=np.float32).reshape(512, 512)
for wc, ww in ((2048.0, 4096.0), (40.0, 400.0), (0.0, 1.0), (1000.0, 3.0)):
    for inv in (False, True):
        ex = window_to_uint8(ramp, wc, ww, inv)
        cv = render_to_rgb(ramp, wc, ww, (COLORMAPS_INV if inv else COLORMAPS)["Gray"])[..., 0]
        d = ex.astype(int) - cv.astype(int)
        n_diff = int((d != 0).sum())
        check(f"A export==canvas CPU wc={wc} ww={ww} inv={inv}", n_diff == 0,
              f"{n_diff}/{d.size} px differ, diff range [{d.min()},{d.max()}], mean {d.mean():+.3f}")
# GPU path (cupy) as the canvas actually uses it
try:
    from viewer_vidi.gpu import GPU
    if GPU.available:
        g = GPU.to_device(ramp)
        ex = window_to_uint8(ramp, 2048.0, 4096.0, False)
        cv = render_to_rgb(g, 2048.0, 4096.0, COLORMAPS["Gray"])[..., 0]
        d = ex.astype(int) - cv.astype(int)
        check("A export==canvas GPU wc=2048 ww=4096", (d == 0).all(), f"{(d!=0).sum()} differ, range [{d.min()},{d.max()}]")
        cv_cpu = render_to_rgb(ramp, 2048.0, 4096.0, COLORMAPS["Gray"])[..., 0]
        check("A canvas GPU == canvas CPU", np.array_equal(cv, cv_cpu), f"{(cv!=cv_cpu).sum()} differ")
    else:
        print("INFO GPU not available")
except Exception as e:
    print("INFO GPU check error", e)

# ── B. constant image (ww from percentiles = 1) ──────────────────────────────
for v in (0.0, 100.0, -1000.0, 4095.0):
    const = np.full((16, 16), v, np.float32)
    wc, ww = wl_from_percentiles(const)
    ex = window_to_uint8(const, wc, ww)
    cv = render_to_rgb(const, wc, ww, COLORMAPS["Gray"])[..., 0]
    check(f"B constant image v={v}: wl=({wc},{ww}) export={ex[0,0]} canvas={cv[0,0]}", ex[0, 0] == cv[0, 0])
d = fresh("const"); const = np.full((16, 16), 7.0, np.float32)
w = export_item(d, ExportInput("c", const, 7.0, 1.0, mask=np.ones((16,16),np.uint8)), ALL)
check("B constant image exports 2 products x 3 formats", len(w) == 6, str(w))
check("B constant nifti value preserved", np.all(rd_nii(os.path.join(d, "nifti", "c_image.nii.gz")) == 7.0))

# ── C. NaN / ±inf ───────────────────────────────────────────────────────────
px = np.linspace(0, 1000, 100, dtype=np.float32).reshape(10, 10)
px[0, 0] = np.nan; px[0, 1] = np.inf; px[0, 2] = -np.inf
with warnings.catch_warnings(record=True) as wl_:
    warnings.simplefilter("always")
    u8 = window_to_uint8(px, 500.0, 1000.0)
    u8i = window_to_uint8(px, 500.0, 1000.0, invert=True)
check("C NaN pixel -> uint8 value", True, f"nan->{u8[0,0]} (inv {u8i[0,0]}), +inf->{u8[0,1]}, -inf->{u8[0,2]}; warnings={[str(x.message) for x in wl_]}")
check("C +inf -> 255 and -inf -> 0", u8[0, 1] == 255 and u8[0, 2] == 0)
check("C NaN cast emits RuntimeWarning (stderr noise in a Qt slot)", not any("invalid value" in str(x.message) for x in wl_), f"{[str(x.message) for x in wl_]}")
d = fresh("nan")
with warnings.catch_warnings(record=True) as wl_:
    warnings.simplefilter("always")
    w = export_item(d, ExportInput("n", px, 500.0, 1000.0, mask=np.ones((10,10),np.uint8), rect=(0,0,5,5)), ALL)
check("C export with NaN/inf writes all products", len(w) == 12, f"{len(w)} written; warnings={[str(x.message) for x in wl_]}")
ni = rd_nii(os.path.join(d, "nifti", "n_image.nii.gz"))
check("C nifti stores NaN and ±inf verbatim", np.isnan(ni[0, 0, 0]) and np.isposinf(ni[1, 0, 0]) and np.isneginf(ni[2, 0, 0]), f"{ni[0,0,0]} {ni[1,0,0]} {ni[2,0,0]}")
p = rd_png(os.path.join(d, "png", "n_image.png"))
check("C png NaN pixel value", True, f"png[0,0]={p[0,0]} jpeg[0,0]={rd_png(os.path.join(d,'jpeg','n_image.jpg'))[0,0]}")
# all-NaN image
allnan = np.full((8, 8), np.nan, np.float32)
with warnings.catch_warnings(record=True) as wl_:
    warnings.simplefilter("always")
    try:
        w = export_item(fresh("allnan"), ExportInput("an", allnan, 0.0, 1.0, mask=np.ones((8,8),np.uint8)), ALL)
        check("C all-NaN image exports without exception", len(w) == 6, f"warnings={len(wl_)}")
    except Exception as e:
        check("C all-NaN image exports without exception", False, repr(e))

# ── D. negative (HU) values, with/without invert ─────────────────────────────
hu = np.array([[-1000, -500, 0, 40, 400, 1000, 3000]], np.float32).repeat(3, 0)
ex = window_to_uint8(hu, 40.0, 400.0)
exi = window_to_uint8(hu, 40.0, 400.0, invert=True)
cv = render_to_rgb(hu, 40.0, 400.0, COLORMAPS["Gray"])[..., 0]
cvi = render_to_rgb(hu, 40.0, 400.0, COLORMAPS_INV["Gray"])[..., 0]
check("D HU soft-tissue window: export row", True, f"export {ex[0].tolist()} canvas {cv[0].tolist()}")
check("D HU invert: export+invert == 255-export", np.array_equal(exi, 255 - ex), f"export_inv {exi[0].tolist()} canvas_inv {cvi[0].tolist()}")
check("D HU below window -> 0, above -> 255", ex[0, 0] == 0 and ex[0, -1] == 255)
d = fresh("hu")
export_item(d, ExportInput("h", hu, 40.0, 400.0, invert=True, mask=np.ones_like(hu, np.uint8)), ALL)
check("D HU nifti keeps negative raw values regardless of invert", np.array_equal(rd_nii(os.path.join(d, "nifti", "h_image.nii.gz"))[:, :, 0].T, hu))
check("D HU png inverted matches window_to_uint8(invert)", np.array_equal(rd_png(os.path.join(d, "png", "h_image.png")), exi))

# ── E. degenerate windows ────────────────────────────────────────────────────
px = np.array([[0, 0.5, 1, 1.5, 2]], np.float32)
for ww in (0.0, 1e-9, -5.0, 1e-6):
    with warnings.catch_warnings(record=True) as wl_:
        warnings.simplefilter("always")
        u = window_to_uint8(px, 1.0, ww)
    check(f"E ww={ww} -> {u[0].tolist()} (no warning)", len(wl_) == 0, f"warnings={[str(x.message) for x in wl_]}")
check("E wc far below data -> all 255", (window_to_uint8(px, -1e9, 10.0) == 255).all())
check("E wc far above data -> all 0", (window_to_uint8(px, 1e9, 10.0) == 0).all())
check("E huge ww (1e30) -> all 128ish", True, f"{window_to_uint8(px, 0.0, 1e30)[0].tolist()}")
big = np.array([[3.0e38, -3.0e38, 0.0]], np.float32)
with warnings.catch_warnings(record=True) as wl_:
    warnings.simplefilter("always")
    u = window_to_uint8(big, 0.0, 1.0)
check("E float32 extremes don't overflow to garbage", u[0, 0] == 255 and u[0, 1] == 0, f"{u[0].tolist()} warnings={[str(x.message) for x in wl_]}")

# ── F. mask dtypes / values ──────────────────────────────────────────────────
pxm = np.zeros((6, 6), np.float32)
cases = {
    "bool": np.eye(6, dtype=bool),
    "int64": np.eye(6, dtype=np.int64),
    "float32_0.5": np.eye(6, dtype=np.float32) * 0.5,
    "uint8_255": np.eye(6, dtype=np.uint8) * 255,
    "int64_256": np.eye(6, dtype=np.int64) * 256,
    "int8_neg": -np.eye(6, dtype=np.int8),
    "float_nan": np.where(np.eye(6, dtype=bool), np.nan, 0.0).astype(np.float32),
}
for name, m in cases.items():
    d = fresh("mask_" + name)
    try:
        with warnings.catch_warnings(record=True) as wl_:
            warnings.simplefilter("always")
            w = export_item(d, ExportInput("m", pxm, 0.0, 1.0, mask=m, rect=(1, 1, 4, 4)), ExportOptions(formats=("png", "nifti")))
        pm = rd_png(os.path.join(d, "png", "m_mask.png")) if w else None
        nm = rd_nii(os.path.join(d, "nifti", "m_mask.nii.gz")) if w else None
        info = f"written={len(w)}; png uniq={np.unique(pm).tolist() if pm is not None else None} n255={(pm==255).sum() if pm is not None else None}; nifti dtype={nm.dtype if nm is not None else None} uniq={np.unique(nm).tolist() if nm is not None else None}; warns={[str(x.message)[:50] for x in wl_]}"
        ok_png = pm is not None and set(np.unique(pm).tolist()) <= {0, 255}
        ok_nii = nm is not None and nm.dtype == np.uint8 and set(np.unique(nm).tolist()) <= {0, 1}
        check(f"F mask {name}: png 0/255 and nifti uint8 0/1", ok_png and ok_nii, info)
    except Exception as e:
        check(f"F mask {name}: no exception", False, repr(e))
# mask shape mismatch (API)
try:
    w = export_item(fresh("mask_shape"), ExportInput("m", pxm, 0.0, 1.0, mask=np.ones((3, 3), np.uint8), rect=(0, 0, 6, 6)), ExportOptions(formats=("png",)))
    check("F mask shape != pixels shape: silently accepted", False, f"written {w}")
except Exception as e:
    check("F mask shape != pixels shape raises", True, repr(e)[:80])

# ── G. rectangles ────────────────────────────────────────────────────────────
pxr = np.arange(20 * 30, dtype=np.float32).reshape(20, 30)
mr = np.zeros((20, 30), np.uint8); mr[5:10, 5:10] = 1
def try_rect(label, rect, expect_shape=None):
    d = fresh("rect")
    try:
        with warnings.catch_warnings(record=True) as wl_:
            warnings.simplefilter("always")
            w = export_item(d, ExportInput("r", pxr, 300.0, 600.0, mask=mr, rect=rect, spacing=(0.5, 0.25)), ALL)
        roi = rd_png(os.path.join(d, "png", "r_roi.png"))
        nroi = nib.load(os.path.join(d, "nifti", "r_roi.nii.gz"))
        info = f"roi png {roi.shape}, nifti {nroi.shape} origin {nroi.affine[:2,3].tolist()}, {len(w)} files, warns={[str(x.message)[:40] for x in wl_]}"
        if expect_shape is not None:
            check(f"G rect {label} {rect}", roi.shape == expect_shape, info)
        else:
            check(f"G rect {label} {rect}: no exception (behaviour)", True, info)
        return roi
    except Exception as e:
        check(f"G rect {label} {rect}: raises", expect_shape is None, f"{type(e).__name__}: {str(e)[:100]}")
        return None
try_rect("full-border", (0, 0, 30, 20), (20, 30))
try_rect("1px-wide", (5, 2, 6, 18), (16, 1))
try_rect("1px-tall", (2, 5, 28, 6), (1, 26))
try_rect("1x1", (3, 3, 4, 4), (1, 1))
try_rect("partly outside positive", (20, 10, 40, 30))
try_rect("partly outside negative", (-5, -5, 10, 10))
try_rect("fully outside", (100, 100, 110, 110))
try_rect("reversed x", (10, 2, 5, 18))
try_rect("zero-area", (5, 5, 5, 5))
try_rect("float coords", (1.0, 2.0, 10.0, 12.0))
try_rect("numpy ints", tuple(np.int64(v) for v in (1, 2, 10, 12)), (10, 9))

# ── H. spacing ───────────────────────────────────────────────────────────────
for sp in ((0.0, 0.0), (None, 1.0), (-1.0, 1.0), (float("nan"), 1.0), (0.5, 0.25), (1e-6, 1e6)):
    d = fresh("spacing")
    try:
        with warnings.catch_warnings(record=True) as wl_:
            warnings.simplefilter("always")
            export_item(d, ExportInput("s", pxr, 300.0, 600.0, mask=mr, rect=(2, 3, 12, 13), spacing=sp), ExportOptions(formats=("nifti",)))
        im = nib.load(os.path.join(d, "nifti", "s_roi.nii.gz"))
        z = im.header.get_zooms(); ao = im.affine[:2, 3]
        check(f"H spacing {sp} -> zooms {tuple(round(float(v),6) for v in z)} roi origin {ao.tolist()}", np.all(np.isfinite(z)) and np.all(np.isfinite(ao)), f"warns={[str(x.message)[:60] for x in wl_]}")
    except Exception as e:
        check(f"H spacing {sp}: raises", False, f"{type(e).__name__}: {str(e)[:120]}")

# ── I. roi_mask empty inside rect ────────────────────────────────────────────
d = fresh("roimask")
w = export_item(d, ExportInput("q", pxr, 300.0, 600.0, mask=mr, rect=(15, 12, 28, 19)), ALL)
rm = rd_png(os.path.join(d, "png", "q_roi_mask.png"))
check("I roi_mask written (all zero) when mask only outside rect", "png/q_roi_mask.png" in w and rm.shape == (7, 13) and rm.max() == 0, f"{w}")
nm = nib.load(os.path.join(d, "nifti", "q_roi_mask.nii.gz"))
check("I nifti roi_mask origin equals rect origin", np.allclose(nm.affine[:2, 3], [15, 12]), str(nm.affine[:2, 3]))

# ── J. stems with separators / '..' (API) ────────────────────────────────────
root = fresh("stem_root"); od = os.path.join(root, "vidi_output")
escape = fresh("stem_escape_target")
rel_escape = os.path.relpath(escape, os.path.join(od, "png"))
try:
    w = export_item(od, ExportInput(rel_escape + "/evil", pxr, 300.0, 600.0, mask=mr), ExportOptions(formats=("png",)))
    outside = sorted(os.listdir(escape))
    check("J stem with '../' cannot write outside out_dir", not outside, f"written={w}; files in escape dir: {outside}")
except Exception as e:
    check("J stem with '../' raises instead of writing", True, repr(e)[:100])
try:
    w = export_item(od, ExportInput("sub/dir/x", pxr, 300.0, 600.0, mask=mr), ExportOptions(formats=("png",)))
    check("J stem with '/' creates nested dirs silently", False, f"written={w}; exists={os.path.exists(os.path.join(od,'png','sub','dir','x_mask.png'))}")
except Exception as e:
    check("J stem with '/' raises", True, repr(e)[:100])
# can unique_stems produce such a stem?
ws_root = fresh("ustem"); os.makedirs(os.path.join(ws_root, "a"), exist_ok=True); os.makedirs(os.path.join(ws_root, "b"), exist_ok=True)
outside_dir = fresh("ustem_outside"); os.makedirs(os.path.join(outside_dir, "deep", "..x"), exist_ok=True)
paths = [os.path.join(ws_root, "a", "img.dcm"), os.path.join(ws_root, "b", "img.dcm"),
         os.path.join(outside_dir, "deep", "..x", "img.dcm"), os.path.join(ws_root, "..img.dcm"), os.path.join(ws_root, "a", "..img.dcm")]
stems = W.unique_stems(paths, ws_root)
check("J unique_stems never yields separators or '..' components", all(os.sep not in s and ".." not in s.split("__")[0][:2] for s in stems) and all(os.sep not in s for s in stems), str(stems))
check("J unique_stems all unique", len(set(stems)) == len(stems), str(stems))
# a dotdot-named file under root with a duplicate: does relpath '..' handling misfire?
stems2 = W.unique_stems([os.path.join(ws_root, "..img.dcm"), os.path.join(ws_root, "a", "..img.dcm")], ws_root)
check("J '..img' basename under root is not treated as outside-root", stems2[0] == "..img" and stems2[1] == "a__..img", str(stems2))

# ── K. unknown format ────────────────────────────────────────────────────────
d = fresh("fmt")
try:
    export_item(d, ExportInput("u", pxr, 300.0, 600.0, mask=mr), ExportOptions(formats=("bogus",)))
    check("K unknown format raises ValueError", False, "no exception")
except ValueError as e:
    check("K unknown format raises ValueError", True, str(e))
try:
    export_item(d, ExportInput("u", pxr, 300.0, 600.0, mask=mr), ExportOptions(formats=("png", "bogus")))
except ValueError:
    pass
left = sorted(os.listdir(os.path.join(d, "png"))) if os.path.isdir(os.path.join(d, "png")) else []
check("K unknown format after a valid one: partial files left on disk (and no manifest row would follow)", not left, f"png files left: {left}")
r = export_item(d, ExportInput("u", pxr, 300.0, 600.0, mask=np.zeros_like(mr)), ExportOptions(formats=("bogus",)))
check("K unknown format with nothing to write: returns [] without raising (validation order)", r == [], str(r))
try:
    export_item(d, ExportInput("u", pxr, 300.0, 600.0, mask=mr), ExportOptions(formats=("PNG",)))
    check("K 'PNG' uppercase accepted", True)
except ValueError as e:
    check("K 'PNG' uppercase rejected (case-sensitive)", True, str(e))

# ── L. JPEG mask after lossy compression ─────────────────────────────────────
rng = np.random.default_rng(0)
H_, W_ = 512, 512
yy, xx = np.mgrid[:H_, :W_]
blob = (((yy - 256) ** 2 + (xx - 256) ** 2) < 120 ** 2).astype(np.uint8)
thin = np.zeros((H_, W_), np.uint8); thin[100, 50:450] = 1; thin[50:450, 400] = 1
spk = (rng.random((H_, W_)) < 0.02).astype(np.uint8)
for name, m in (("disc", blob), ("thin-lines", thin), ("2%-speckle", spk)):
    d = fresh("jpg_" + name)
    export_item(d, ExportInput("j", np.zeros((H_, W_), np.float32), 0.0, 1.0, mask=m), ExportOptions(formats=("jpeg", "png")))
    j = rd_png(os.path.join(d, "jpeg", "j_mask.jpg")); p = rd_png(os.path.join(d, "png", "j_mask.png"))
    not_bin = int(((j != 0) & (j != 255)).sum()); flipped = int(((j > 127) != (p > 127)).sum())
    check(f"L jpeg mask {name}: {not_bin} px not 0/255 ({100*not_bin/j.size:.2f}%), {flipped} px flip at thr 127 (of {int(m.sum())} fg)", flipped == 0)

# ── M. pixel dtype / layout ──────────────────────────────────────────────────
base = np.arange(40 * 30, dtype=np.float32).reshape(40, 30)
ref = fresh("dtype_ref"); export_item(ref, ExportInput("d", base, 600.0, 1200.0, mask=mr.repeat(2, 0)[:40, :30], rect=(3, 4, 20, 30)), ALL)
for name, arr in (("flipud view", np.flipud(np.flipud(base))), ("float64", base.astype(np.float64)), ("int16", base.astype(np.int16)), ("uint16", base.astype(np.uint16)), ("fortran", np.asfortranarray(base))):
    d = fresh("dtype_" + name.replace(" ", "_"))
    try:
        export_item(d, ExportInput("d", arr, 600.0, 1200.0, mask=mr.repeat(2, 0)[:40, :30], rect=(3, 4, 20, 30)), ALL)
        same = all(np.array_equal(rd_png(os.path.join(d, f, "d_" + s)), rd_png(os.path.join(ref, f, "d_" + s))) for f, s in (("png", "image.png"), ("png", "roi.png"), ("jpeg", "roi.jpg"))) and \
               all(np.array_equal(rd_nii(os.path.join(d, "nifti", "d_" + s)), rd_nii(os.path.join(ref, "nifti", "d_" + s))) for s in ("image.nii.gz", "roi.nii.gz", "roi_mask.nii.gz"))
        ndt = nib.load(os.path.join(d, "nifti", "d_image.nii.gz")).get_data_dtype()
        check(f"M pixels {name}: outputs identical to float32 C-order, nifti dtype {ndt}", same and ndt == np.float32)
    except Exception as e:
        check(f"M pixels {name}: no exception", False, repr(e)[:100])
# 3-D pixels by mistake (API)
try:
    export_item(fresh("dtype_3d"), ExportInput("d", np.zeros((4, 5, 6), np.float32), 0.0, 1.0, mask=np.ones((4, 5, 6), np.uint8)), ExportOptions(formats=("png",)))
    check("M 3-D pixels accepted silently", False)
except Exception as e:
    check("M 3-D pixels raise", True, f"{type(e).__name__}: {str(e)[:80]}")

# ── N. 8192x8192 timing ──────────────────────────────────────────────────────
bigpx = (rng.random((8192, 8192), dtype=np.float32) * 4095).astype(np.float32)
bigm = np.zeros((8192, 8192), np.uint8); bigm[2000:6000, 2000:6000] = 1
for fmt in FORMATS:
    d = fresh("big_" + fmt)
    t0 = time.time()
    w = export_item(d, ExportInput("b", bigpx, 2048.0, 4096.0, mask=bigm, rect=(100, 100, 8000, 8000)), ExportOptions(formats=(fmt,), save_image=True))
    dt = time.time() - t0
    sz = sum(os.path.getsize(os.path.join(d, p)) for p in w) / 1e6
    check(f"N 8192² {fmt}: 4 products in {dt:.1f}s, {sz:.1f} MB", dt < 120, str(w))
    shutil.rmtree(d, ignore_errors=True)
del bigpx, bigm

n_fail = sum(1 for _, ok in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} checks passed")
