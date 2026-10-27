"""No-Qt portability probes: unique_stems case collision, out-dir with separator,
manifest BOM / extra column / trailing comma, csv newline handling, NEP50 uint8."""
import os, sys, shutil, csv, traceback
from common import *
import harness as H
H.register_package()
import numpy as np
from viewer_vidi import workspace as W
from viewer_vidi.annotation_export import ExportInput, ExportOptions, export_item

D = os.path.join(SCR, "data", "ws_case"); shutil.rmtree(D, ignore_errors=True); os.makedirs(D)
src = os.path.join(FIX, sorted(os.listdir(FIX))[0])

# ── 1. case-only differing stems (macOS / Windows collision) ─────────────────
os.makedirs(os.path.join(D, "sub1")); os.makedirs(os.path.join(D, "sub2"))
shutil.copy(src, os.path.join(D, "sub1", "Case.dcm"))
shutil.copy(src, os.path.join(D, "sub2", "case.dcm"))
imgs, _ = W.probe_workspace(D)
ws = W.build_workspace(D, "image", imgs)
stems = [it.stem for it in ws.items]
lowered = [s.lower() for s in stems]
check("case-only stems differ on Linux", stems == ["Case", "case"], str(stems))
check("case-insensitive collision: lowercased stems collide (macOS/Win overwrite)",
      len(set(lowered)) == len(lowered), f"stems={stems} lower={lowered}")
# emulate: write both products into the same out dir and show the filenames differ only by case
px = np.zeros((10, 10), np.float32); m = np.ones((10, 10), np.uint8)
for s in stems:
    export_item(ws.out_dir, ExportInput(stem=s, pixels=px, wc=1, ww=1, mask=m), ExportOptions(formats=("png",)))
names = sorted(os.listdir(os.path.join(ws.out_dir, "png")))
print("png dir:", names)
check("on Linux two files written; on APFS/NTFS the 2nd would overwrite the 1st",
      names == ["Case_mask.png", "case_mask.png"], str(names))

# ── 2. out dir name containing a path separator ──────────────────────────────
D2 = os.path.join(SCR, "data", "ws_sep"); shutil.rmtree(D2, ignore_errors=True); os.makedirs(D2)
shutil.copy(src, os.path.join(D2, "a.dcm"))
out_name = "out/png"   # survives _out_name(): strip('/\\') only trims the ends
name = out_name.strip().strip("/\\")
check("_out_name keeps inner separator", name == "out/png", name)
imgs, _ = W.probe_workspace(D2, name)
ws2 = W.build_workspace(D2, "image", imgs, name)
written = export_item(ws2.out_dir, ExportInput(stem="a", pixels=px, wc=1, ww=1, mask=m), ExportOptions(formats=("png",)))
W.write_manifest_row(ws2.manifest_path, dict(stem="a", source=ws2.items[0].path, files=" ".join(written)))
print("written:", written, "out_dir:", ws2.out_dir)
imgs2, _ = W.probe_workspace(D2, name)
rel = [os.path.relpath(p, D2) for p in imgs2]
check("reopen with out dir 'out/png': exported masks are NOT rescanned as items",
      rel == ["a.dcm"], str(rel))
ws3 = W.build_workspace(D2, "image", imgs2, name)
print("reopen items:", [(it.stem, it.done) for it in ws3.items])

# ── 2b. out dir '../x' escapes the workspace; absolute path becomes relative ──
for raw in ("../escape", "/abs/path", "C:\\out", " vidi_output /"):
    nm = raw.strip().strip("/\\")
    print(f"_out_name({raw!r}) -> {nm!r} -> out_dir {os.path.normpath(os.path.join(D2, nm))!r}")
check("'../escape' resolves OUTSIDE the workspace root",
      not os.path.normpath(os.path.join(D2, "../escape")).startswith(D2 + os.sep), "")

# ── 3. manifest round trips ──────────────────────────────────────────────────
D3 = os.path.join(SCR, "data", "manifest"); shutil.rmtree(D3, ignore_errors=True); os.makedirs(D3)
mp = os.path.join(D3, "manifest.csv")
weird_source = os.path.join(D3, 'odd, "name"\nwith newline.dcm')
W.write_manifest_row(mp, dict(stem="s1", source=weird_source, saved_at="t", mask_pixels=3,
                              x0=1, y0=2, x1=3, y1=4, formats="png", files="png/s1_mask.png"))
W.write_manifest_row(mp, dict(stem="s2", source="plain", mask_pixels=0))
rows = W.read_manifest(mp)
check("csv newline='': source with comma/quote/newline round-trips", rows["s1"]["source"] == weird_source, repr(rows["s1"]["source"]))
raw = open(mp, "rb").read()
check("manifest line terminator is CRLF (csv default) and no stray blank lines",
      raw.count(b"\r\n") >= 3 and b"\r\r\n" not in raw, repr(raw[:80]))
check("replace keeps 2 rows, no .tmp left", len(rows) == 2 and not os.path.exists(mp + ".tmp"), str(sorted(os.listdir(D3))))

# 3a. BOM-prefixed manifest (Excel 'CSV UTF-8' save)
with open(mp, "rb") as f: body = f.read()
with open(mp, "wb") as f: f.write(b"\xef\xbb\xbf" + body)
rows_bom = W.read_manifest(mp)
check("BOM manifest: read_manifest still finds the 2 rows", len(rows_bom) == 2, f"got {len(rows_bom)} rows: {list(rows_bom)}")
W.write_manifest_row(mp, dict(stem="s3", source="x"))
rows_after = W.read_manifest(mp)
check("BOM manifest: previous rows survive the next save", {"s1", "s2", "s3"} <= set(rows_after), f"rows now {sorted(rows_after)}")

# 3b. extra column added by the user (e.g. 'notes' in Excel)
with open(mp, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(list(W.MANIFEST_FIELDS) + ["notes"])
    w.writerow(["s1", "src", "t", "3", "1", "2", "3", "4", "png", "png/s1_mask.png", "my note"])
try:
    W.write_manifest_row(mp, dict(stem="s2", source="y"))
    check("extra manifest column: write_manifest_row does not raise", True)
except Exception as e:
    check("extra manifest column: write_manifest_row does not raise", False, f"{type(e).__name__}: {e}")
    traceback.print_exc(file=sys.stdout)
print("after extra-column write:", sorted(os.listdir(D3)))

# 3c. a data row with a trailing comma (one more cell than the header)
with open(mp, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(list(W.MANIFEST_FIELDS))
    f.write("s1,src,t,3,1,2,3,4,png,png/s1_mask.png,\r\n")
try:
    W.write_manifest_row(mp, dict(stem="s2", source="y"))
    check("trailing-comma row: write_manifest_row does not raise", True)
except Exception as e:
    check("trailing-comma row: write_manifest_row does not raise", False, f"{type(e).__name__}: {e}")
print("after trailing-comma write:", sorted(os.listdir(D3)))

# 3d. row with FEWER cells than the header (user deleted a cell)
with open(mp, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(list(W.MANIFEST_FIELDS))
    f.write("s1,src\r\n")
try:
    W.write_manifest_row(mp, dict(stem="s2", source="y"))
    rows = W.read_manifest(mp)
    check("short row: write ok and s1 kept", "s1" in rows and "s2" in rows, str(sorted(rows)))
except Exception as e:
    check("short row: write_manifest_row does not raise", False, f"{type(e).__name__}: {e}")

# ── 4. NEP 50: uint8 * 110 ───────────────────────────────────────────────────
mk = np.array([0, 1, 2, 3], np.uint8)
prod = mk * 110
print("uint8*110 ->", prod, prod.dtype)
check("NEP50: uint8 mask*110 stays uint8, 0/1 → 0/110 exact", prod.dtype == np.uint8 and list(prod[:2]) == [0, 110])
check("NEP50: a value 3 would wrap (330→74) — only matters if mask ever holds >2", prod[3] == 74, str(prod))

# ── 5. unique_stems relpath '..' branch & os.sep replacement ─────────────────
st = W.unique_stems(["/x/y/a.dcm", "/x/z/a.dcm"], "/x/y")
check("unique_stems outside-root fallback uses full path with '__'", st[0] == "a" and st[1].startswith("x__z__a"), str(st))
st2 = W.unique_stems(["/r/a.dcm", "/r/s/a.dcm", "/r/s/t/a.dcm"], "/r")
check("unique_stems nested dirs", st2 == ["a", "s__a", "s__t__a"], str(st2))
st3 = W.unique_stems(["/r/a.dcm", "/r/a.png"], "/r")
check("same stem different ext in same dir → numeric suffix", st3 == ["a", "a_1"], str(st3))
# same basename in same dir can't happen; but 'a__b.dcm' in root vs 'a/b.dcm' both map to 'a__b'
st4 = W.unique_stems(["/r/a__b.dcm", "/r/a/b.dcm", "/r/c/b.dcm"], "/r")
check("'a__b.dcm' vs 'a/b.dcm' resolved by numeric suffix", len(set(st4)) == 3, str(st4))

sys.exit(summary())
