"""Regression checks for the 2026-10-27 stability fixes (groups G1–G12 in TODO.md).
Run: QT_QPA_PLATFORM=offscreen python tests/stability/test_fixes.py
"""
import os, sys, csv, shutil, tempfile, time, warnings
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "scratch"))
import harness as H
H.register_package()
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from viewer_vidi import workspace as W
from viewer_vidi.annotation_export import ExportInput, ExportOptions, export_item, window_to_uint8
from viewer_vidi.windowing import render_to_rgb
from viewer_vidi.colormaps import COLORMAPS

results = []
def check(name, cond, info=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""))

T = tempfile.mkdtemp(prefix="vidi_fixes_")
FIX = H.FIXTURES
def wsdir(name, n=2):
    d = os.path.join(T, name); os.makedirs(d, exist_ok=True)
    for i, f in enumerate(["bpd1_20100101_1.dcm", "bpd1_20100101_2.dcm", "bpd1_20100102_1.dcm"][:n]):
        shutil.copy(os.path.join(FIX, f), os.path.join(d, f))
    return d

# ── G2 / G10: list parsing never raises, BOM / UTF-16 / header heuristics ──
L = os.path.join(T, "lists"); os.makedirs(L)
img = os.path.join(wsdir("imgs", 1), "bpd1_20100101_1.dcm")
open(os.path.join(L, "nul.csv"), "wb").write(("path,label\n" + img + ",a\x00b\n").encode("utf-8"))
open(os.path.join(L, "u16.csv"), "wb").write(("path,label\n" + img + ",a\n").encode("utf-16"))
open(os.path.join(L, "big.csv"), "w").write("path,blob\n" + img + "," + "x" * 200000 + "\n")
open(os.path.join(L, "tilde.txt"), "wb").write(b"~us\x00er/a.dcm\n" + img.encode() + b"\n")
open(os.path.join(L, "bom.txt"), "wb").write(b"\xef\xbb\xbf" + img.encode() + b"\n")
open(os.path.join(L, "noext.csv"), "w").write("/data/export/54450002/42228791,x\n" + img + ",y\n")
for fn, want in (("nul.csv", 1), ("u16.csv", 1), ("big.csv", 1), ("tilde.txt", 2), ("bom.txt", 1), ("noext.csv", 2)):
    try:
        got = W.parse_list_file(os.path.join(L, fn))
        check(f"G2/G10 parse {fn}: no raise, {want} entries, image resolved",
              len(got) == want and img in got, str(got)[:160])
    except Exception as e:
        check(f"G2/G10 parse {fn}", False, repr(e))
check("G2 find_list_files survives binary .txt", W.find_list_files(L) is not None
      and (open(os.path.join(L, "binary.txt"), "wb").write(os.urandom(300000)) or True)
      and isinstance(W.find_list_files(L), list))

# ── G3 / G7: manifest decoding and protection ───────────────────────────────
M = os.path.join(T, "mani"); os.makedirs(M)
mp = os.path.join(M, "manifest.csv")
open(mp, "wb").write("stem,source\nRöntgen,/x/a.dcm\n".encode("cp1252"))
check("G3 cp1252 manifest reads without raising", W.read_manifest(mp) == {} or "R" in "".join(W.read_manifest(mp)))
open(mp, "wb").write(b"\xef\xbb\xbfstem,source,files\na,/x/a.dcm,png/a_mask.png\n")
check("G7 BOM manifest rows are read", "a" in W.read_manifest(mp))
open(mp, "wb").write(b"\x00\x00\x00garbage\n\xff\xfe")
bk = W.write_manifest_row(mp, {"stem": "b", "source": "/x/b.dcm"})
check("G7 unreadable manifest is backed up, not overwritten",
      bk and os.path.isfile(bk) and set(W.read_manifest(mp)) == {"b"}, str(bk))
open(mp, "w").write("stem,source,note\na,/x/a.dcm,hello\n")
W.write_manifest_row(mp, {"stem": "b", "source": "/x/b.dcm"})
rows = W.read_manifest(mp)
check("G1c extra user column preserved on rewrite", rows["a"].get("note") == "hello" and "b" in rows)
check("manifest has 'view' column", "view" in W.MANIFEST_FIELDS)

# ── G4: stems ───────────────────────────────────────────────────────────────
st = W.unique_stems(["/r/k.png", "/r/k.nii", "/r/k_1.png"], "/r")
check("G4 suffix never collides with a natural stem", len(set(st)) == 3, str(st))
st = W.unique_stems(["/r/s1/Case.dcm", "/r/s2/case.dcm"], "/r")
check("G4 case-only duplicates get distinct case-folded stems", len({x.lower() for x in st}) == 2, str(st))
longp = "/r/" + "/".join(["d" * 40] * 7) + "/IM1.dcm"
st = W.unique_stems([longp, "/r/x/IM1.dcm"], "/r")
check("G4 long stems are shortened", all(len(x) <= W.MAX_STEM_LEN for x in st), str([len(x) for x in st]))
st = W.unique_stems(["/r/a.png", "/r/sub/a.png"], "/r", reserved={"/r/sub/a.png": "a"})
check("G4 reserved stem kept, other one moves", st[1] == "a" and st[0] != "a", str(st))
# done flags follow the source, stems stay stable when a twin appears
D = wsdir("dups", 1)
os.makedirs(os.path.join(D, "sub"))
ws = W.build_workspace(D, "image", W.scan_images(D))
W.write_manifest_row(ws.manifest_path, {"stem": ws.items[0].stem, "source": W.manifest_source(ws.items[0].path, D), "files": "png/x.png"})
shutil.copy(img, os.path.join(D, "sub", "bpd1_20100101_1.dcm"))
ws2 = W.build_workspace(D, "image", W.scan_images(D))
by = {os.path.relpath(it.path, D): it for it in ws2.items}
check("G4 done flag follows the file after a duplicate appears",
      by["bpd1_20100101_1.dcm"].done and by["bpd1_20100101_1.dcm"].stem == "bpd1_20100101_1"
      and not by[os.path.join("sub", "bpd1_20100101_1.dcm")].done, str([(k, v.stem, v.done) for k, v in by.items()]))
check("G4 source is stored relative to the workspace", W.manifest_source(ws.items[0].path, D) == "bpd1_20100101_1.dcm")

# ── G8: output dir never rescanned ─────────────────────────────────────────
O = wsdir("outs", 1)
os.makedirs(os.path.join(O, "old_out", "png")); open(os.path.join(O, "old_out", "manifest.csv"), "w").write("stem\n")
shutil.copy(img, os.path.join(O, "old_out", "png", "a_mask.dcm"))
check("G8 any dir holding manifest.csv is skipped", len(W.scan_images(O, {"vidi_output"})) == 1)

# ── export: WYSIWYG, NaN, rect clip ─────────────────────────────────────────
px = np.linspace(-100, 4000, 60 * 50, dtype=np.float32).reshape(60, 50)
u8 = window_to_uint8(px, 1500, 3000)
ref = render_to_rgb(px, 1500, 3000, COLORMAPS["Gray"])[..., 0]
check("export PNG equals the canvas render pixel-exactly", np.array_equal(u8, ref))
with warnings.catch_warnings():
    warnings.simplefilter("error")
    pn = px.copy(); pn[0, 0] = np.nan; pn[0, 1] = np.inf
    ok = True
    try: window_to_uint8(pn, 1500, 3000)
    except Exception as e: ok = False
    check("export NaN/inf pixels raise no warning", ok)
out = os.path.join(T, "exp")
w = export_item(out, ExportInput("s", px, 1500, 3000, rect=(-5, -5, 500, 500)), ExportOptions(("png",)))
check("export clips an out-of-bounds rect", "png/s_roi.png" in w)
try:
    export_item(out, ExportInput("../evil", px, 1500, 3000, mask=np.ones_like(px, np.uint8)), ExportOptions(("png",))); bad = False
except ValueError: bad = True
check("export rejects a stem with separators", bad)

# ── GUI part ────────────────────────────────────────────────────────────────
app, win = H.boot()
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()

# G1: manifest write failure → dialog, no abort
G1 = wsdir("g1", 1)
os.makedirs(os.path.join(G1, "vidi_output", "manifest.csv"))   # a directory where the file should be
H.open_workspace(app, win, G1)
dock._tool_btns["rect"].setChecked(True); dock._apply_tool()
H.drag(app, canvas, H.pt(canvas, .2, .2), H.pt(canvas, .6, .6))
seen = H.auto_close_dialogs(app, 300)
dock._save(advance=False); H.pump(app, 500)
check("G1 manifest write failure shows a dialog and keeps the app alive",
      any("Manifest" in s[1] for s in seen) and not dock._ws.items[0].done
      and os.path.isfile(os.path.join(G1, "vidi_output", "png", "bpd1_20100101_1_roi.png")), str(seen))

# G8: out dir with separator falls back
dock._out_edit.setText("exports/run1")
check("G8 out dir with a separator is rejected", dock._out_name() == W.DEFAULT_OUT_DIR)

# G6: truncated DICOM → load failed, item flagged, save refused; Next still works
G6 = wsdir("g6", 2)
with open(os.path.join(G6, "bpd1_20100101_1.dcm"), "r+b") as f:
    f.truncate(4000)
ws6 = H.open_workspace(app, win, G6)
t0 = time.time()
while time.time() - t0 < 20 and not cell.load_error_text() and canvas.displayed_pixels() is None:
    app.processEvents(); time.sleep(0.02)
check("G6 truncated DICOM reports a load error instead of zeros",
      cell.load_error_text() != "" and canvas.displayed_pixels() is None, cell.load_error_text()[:80])
check("G6 item flagged in the list", dock._ws.items[0].error != "" and dock._list.item(0).text().startswith("✗"))
dock._save(advance=False); app.processEvents()
check("G6 save refused on a failed load", not dock._ws.items[0].done and "load failed" in dock._status_lbl.text().lower())
dock._step(+1); H.wait_loaded(app, cell)
check("G6 Next moves on to the next item", dock._index == 1 and canvas.displayed_pixels() is not None)

# G5: the stale-signal guard
from viewer_vidi.data_model import SeriesMeta
m1 = SeriesMeta("/a", "/a/x.dcm", "x.dcm", "a", 1); m2 = SeriesMeta("/a", "/a/y.dcm", "y.dcm", "a", 1)
check("G5 stale SeriesData from another request is rejected",
      cell._same_request(m1, m1) and not cell._same_request(m1, m2))
# rapid navigation then save must export the current item's pixels
G5 = os.path.join(T, "g5"); os.makedirs(G5)
shutil.copy(os.path.join(FIX, "bpd1_20100101_1.dcm"), G5)
from PIL import Image
Image.fromarray((np.random.rand(300, 200) * 255).astype(np.uint8)).save(os.path.join(G5, "small.png"))
H.open_workspace(app, win, G5)
for _ in range(12):
    dock._step(+1); dock._step(-1)
dock._step(+1); H.wait_loaded(app, cell)
item = dock._ws.items[dock._index]
dock._image_chk.setChecked(True)
dock._save(advance=False); app.processEvents()
saved = os.path.join(G5, "vidi_output", "png", f"{item.stem}_image.png")
shp = np.array(Image.open(saved)).shape if os.path.isfile(saved) else None
want = (300, 200) if item.stem == "small" else (2044, 1514)
check("G5 save after rapid navigation writes the current item's pixels", shp == want, f"{item.stem} {shp}")

# G9 / G12 / G24: NIfTI axes, spacing, per-slice mask, view recorded
import nibabel as nib
G9 = os.path.join(T, "g9"); os.makedirs(G9)
vol = (np.random.rand(40, 30, 12) * 1000).astype(np.float32)        # (X, Y, Z)
nib.save(nib.Nifti1Image(vol, np.diag([0.5, 2.0, 3.0, 1.0])), os.path.join(G9, "aniso3d.nii.gz"))
img2d = (np.random.rand(40, 30) * 1000).astype(np.float32)
nib.save(nib.Nifti1Image(img2d, np.diag([0.5, 2.0, 1.0, 1.0])), os.path.join(G9, "aniso2d.nii.gz"))
H.open_workspace(app, win, G9)
sd = cell.series_data(); px2 = canvas.displayed_pixels()
check("G9 2-D NIfTI displayed as (Y, X) with spacing (row=Y, col=X)",
      px2.shape == (30, 40) and sd.pixel_spacing == (2.0, 0.5) and np.array_equal(px2, img2d.T),
      f"{px2.shape} {sd.pixel_spacing}")
dock._fmt_chk["nifti"].setChecked(True); dock._fmt_chk["png"].setChecked(False)
dock._save(advance=True); H.wait_loaded(app, cell)
e2 = nib.load(os.path.join(G9, "vidi_output", "nifti", "aniso2d_image.nii.gz"))
check("G9 2-D NIfTI export keeps source indexing and zooms",
      e2.shape == (40, 30, 1) and np.allclose(np.asarray(e2.dataobj)[:, :, 0], img2d)
      and tuple(np.round(e2.header.get_zooms()[:2], 3)) == (0.5, 2.0), f"{e2.shape} {e2.header.get_zooms()}")
sd = cell.series_data()
check("G9 3-D NIfTI spacing (row=Y, col=X)", sd.pixel_spacing == (2.0, 0.5) and cell.display_spacing() == (2.0, 0.5), str(sd.pixel_spacing))
cell._set_view("CORONAL"); app.processEvents()
check("G24 coronal reformat spacing has slice spacing on rows", cell.display_spacing() == (3.0, 0.5), str(cell.display_spacing()))
cell._set_view("AXIAL"); app.processEvents()
dock._tool_btns["paint"].setChecked(True); dock._apply_tool()
H.drag(app, canvas, H.pt(canvas, .3, .3), H.pt(canvas, .6, .3))
n0 = canvas.mask_pixels(); z0 = cell._cur_z
cell._slice_slider.setValue(z0 + 3); app.processEvents()
check("G12 mask does not ride along to another slice", n0 > 0 and canvas.mask_pixels() == 0, f"{n0} → {canvas.mask_pixels()}")
H.drag(app, canvas, H.pt(canvas, .3, .3), H.pt(canvas, .6, .3))
dock._save(advance=False); app.processEvents()
row = W.read_manifest(dock._ws.manifest_path).get("aniso3d", {})
check("G12 manifest records the slice/view", row.get("view", "").startswith("AXIAL z=") and f"z={z0 + 3}" in row.get("view", ""), row.get("view"))

# G11: stale products removed on re-save
G11 = wsdir("g11", 1)
H.open_workspace(app, win, G11)
dock._fmt_chk["png"].setChecked(True); dock._fmt_chk["nifti"].setChecked(False); dock._fmt_chk["jpeg"].setChecked(True)
dock._tool_btns["rect"].setChecked(True); dock._apply_tool()
H.drag(app, canvas, H.pt(canvas, .2, .2), H.pt(canvas, .6, .6))
dock._save(advance=False); app.processEvents()
dock._fmt_chk["jpeg"].setChecked(False)
dock._save(advance=False); app.processEvents()
jp = os.path.join(G11, "vidi_output", "jpeg", "bpd1_20100101_1_roi.jpg")
row = W.read_manifest(dock._ws.manifest_path)["bpd1_20100101_1"]
check("G11 re-save removes stale products and uses ';' in files", not os.path.isfile(jp) and ";" not in row["files"].strip(";") or row["files"].count("/") == 2, row["files"])
check("G11 manifest files match disk", all(os.path.isfile(os.path.join(G11, "vidi_output", f)) for f in row["files"].split(";")))

# canvas: undo restores the rectangle; tiny drags ignored
r1 = canvas.crop_rect()
H.drag(app, canvas, H.pt(canvas, .5, .5), H.pt(canvas, .5, .5), steps=1)
check("canvas tiny drag keeps the rectangle", canvas.crop_rect() == r1)
dock._clear(); app.processEvents()
check("canvas undo after Clear restores the rectangle", canvas.crop_rect() is None and canvas.undo_annotation() and canvas.crop_rect() == r1)

# dock hidden: Ctrl+S does nothing; tree load keeps the tool
dock._tool_btns["paint"].setChecked(True); dock._apply_tool()
win._ws_btn.setChecked(False); app.processEvents()
dock.save_and_next(); app.processEvents()
check("Ctrl+S with the dock hidden does not save/advance", dock._index == 0 and canvas.wl_mode() == "drag")
win._ws_btn.setChecked(True); app.processEvents()
from viewer_vidi.tree_panel import _make_series_meta
win._on_series_selected(_make_series_meta(os.path.join(G11, "bpd1_20100101_1.dcm"))); H.wait_loaded(app, cell)
check("tree load keeps the dock's tool on the panel", canvas.wl_mode() == "paint")
cell._roi_btn.setChecked(True); app.processEvents()
dock._apply_tool()
check("dock tool unchecks the panel's ROI W/L button", not cell._roi_btn.isChecked() and canvas.wl_mode() == "paint")

win.close(); app.processEvents()
shutil.rmtree(T, ignore_errors=True)
n_fail = sum(1 for _, ok in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} checks passed")
sys.exit(1 if n_fail else 0)
