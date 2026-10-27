"""Pure-Python manifest tests (workspace.read_manifest / write_manifest_row / build_workspace)."""
import os, sys, time, shutil, csv, subprocess, traceback
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
H.register_package()
from viewer_vidi import workspace as W

D = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/manifest"
T = os.path.join(D, "pure"); shutil.rmtree(T, ignore_directories=True) if False else shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
res = []
def check(name, cond, info=""):
    res.append((name, bool(cond))); print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""))

def row(stem, **kw):
    r = dict(stem=stem, source=f"/x/{stem}.png", saved_at="2026-10-26T00:00:00", mask_pixels=5,
             x0=1, y0=2, x1=3, y1=4, formats="png", files=f"png/{stem}_mask.png")
    r.update(kw); return r

def try_call(fn, *a):
    try: return fn(*a), None
    except Exception as e: return None, e

GOOD = "stem,source,saved_at,mask_pixels,x0,y0,x1,y1,formats,files\r\na,/x/a.png,2026-10-26T00:00:00,5,1,2,3,4,png,png/a_mask.png\r\nb,/x/b.png,2026-10-26T00:00:00,0,,,,,png,png/b_image.png\r\n"

def mk(name, content, mode="w", **kw):
    p = os.path.join(T, name); os.makedirs(p, exist_ok=True); m = os.path.join(p, "manifest.csv")
    with open(m, mode, **({"newline": ""} if "b" not in mode else {}), **kw) as f: f.write(content)
    return m

# 1. truncated last line (power loss mid-write of a non-atomic editor; with os.replace this needs an external cause)
m = mk("trunc", GOOD[:-20])
r, e = try_call(W.read_manifest, m)
check("truncated last line: read does not raise, keeps 'a'", e is None and "a" in r, f"{e!r} {r and list(r)}")
r2, e2 = try_call(W.write_manifest_row, m, row("c"))
r3 = W.read_manifest(m)
check("truncated: write_manifest_row does not raise, result has a,b,c", e2 is None and set(r3) == {"a","b","c"}, f"{e2!r} {sorted(r3)}")

# 2. missing header (first line deleted)
m = mk("nohdr", GOOD.split("\r\n",1)[1])
r, e = try_call(W.read_manifest, m)
check("missing header: read returns {} without raising", e is None and r == {}, f"{e!r} {r}")
r2, e2 = try_call(W.write_manifest_row, m, row("c"))
r3 = W.read_manifest(m)
check("missing header: write does not raise; previous rows LOST (now only 'c')", e2 is None and set(r3) == {"c"}, f"{e2!r} {sorted(r3)}")

# 3. extra/unknown column in header (user added a 'note' column in Excel)
m = mk("extracol", "stem,source,saved_at,mask_pixels,x0,y0,x1,y1,formats,files,note\r\na,/x/a.png,t,5,1,2,3,4,png,png/a_mask.png,hello\r\n")
r, e = try_call(W.read_manifest, m)
check("extra column: read ok", e is None and "a" in r and r["a"].get("note") == "hello", f"{e!r}")
r2, e2 = try_call(W.write_manifest_row, m, row("c"))
check("extra column: write_manifest_row RAISES", e2 is not None, f"{type(e2).__name__ if e2 else None}: {e2}")
check("extra column: manifest.csv untouched after failed write (tmp left behind?)", os.path.isfile(m), f"tmp exists={os.path.exists(m+'.tmp')}")

# 3b. a data row with MORE fields than the header (stray comma in a hand edit)
m = mk("extrafield", "stem,source,saved_at,mask_pixels,x0,y0,x1,y1,formats,files\r\na,/x/a.png,t,5,1,2,3,4,png,png/a_mask.png,oops\r\n")
r, e = try_call(W.read_manifest, m)
r2, e2 = try_call(W.write_manifest_row, m, row("c"))
check("row with extra field: read ok, write RAISES", e is None and e2 is not None, f"read={e!r} write={type(e2).__name__ if e2 else None}: {e2}")

# 4. older schema lacking 'files' column
m = mk("oldschema", "stem,source,saved_at,mask_pixels,x0,y0,x1,y1,formats\r\na,/x/a.png,t,5,1,2,3,4,png\r\n")
r, e = try_call(W.read_manifest, m)
r2, e2 = try_call(W.write_manifest_row, m, row("c"))
r3 = W.read_manifest(m)
check("old schema (no 'files'): read ok, write ok, upgraded with files='' for a", e is None and e2 is None and set(r3)=={"a","c"} and r3["a"]["files"]=="", f"{e!r} {e2!r} {r3}")

# 5. empty file
m = mk("empty", "")
r, e = try_call(W.read_manifest, m); r2, e2 = try_call(W.write_manifest_row, m, row("c"))
check("empty manifest: read {}, write ok", e is None and r == {} and e2 is None and set(W.read_manifest(m))=={"c"}, f"{e!r} {e2!r}")

# 5b. header only
m = mk("hdronly", GOOD.split("\r\n",1)[0] + "\r\n")
r, e = try_call(W.read_manifest, m); check("header-only manifest: read {}", e is None and r == {}, f"{e!r}")

# 6. non-UTF-8 bytes (latin-1 path in 'source')
m = mk("latin1", GOOD.encode().replace(b"/x/a.png", "/x/\xe4.png".encode("latin-1")), mode="wb")
r, e = try_call(W.read_manifest, m)
check("non-UTF-8 bytes: read_manifest RAISES (not caught)", e is not None, f"{type(e).__name__ if e else None}: {e}")
ws, e2 = try_call(W.build_workspace, T, "image", [], "latin1")   # manifest at T/latin1/manifest.csv
check("non-UTF-8 bytes: build_workspace RAISES", e2 is not None, f"{type(e2).__name__ if e2 else None}: {e2}")

# 6b. NUL bytes (zero-filled tail, classic ext4 crash artefact)
m = mk("nul", GOOD.encode() + b"\x00" * 512, mode="wb")
r, e = try_call(W.read_manifest, m)
check("NUL-filled tail: read_manifest RAISES (not caught)", e is not None, f"{type(e).__name__ if e else None}: {e}")
r2, e2 = try_call(W.write_manifest_row, m, row("c"))
check("NUL-filled tail: write_manifest_row RAISES", e2 is not None, f"{type(e2).__name__ if e2 else None}: {e2}")

# 6c. UTF-8 BOM (manifest re-saved by Excel)
m = mk("bom", GOOD, encoding="utf-8-sig")
r, e = try_call(W.read_manifest, m)
check("BOM manifest (Excel 'CSV UTF-8'): rows found", e is None and set(r) == {"a","b"}, f"{e!r} {r and sorted(r)}")
r2, e2 = try_call(W.write_manifest_row, m, row("c"))
r3 = W.read_manifest(m)
check("BOM manifest: write keeps a,b", e2 is None and set(r3) == {"a","b","c"}, f"{e2!r} {sorted(r3)}")

# 7. unicode stems + comma/quote/space stems round trip
m = os.path.join(T, "odd", "manifest.csv")
odd = ["ärger_über", "日本語", "comma,stem", 'quote"stem', "space stem", "new\nline"]
for s in odd: W.write_manifest_row(m, row(s, source=f"/p/{s}.png", files=f"png/{s}_mask.png png/{s}_roi.png"))
r = W.read_manifest(m)
check("odd stems: all round-trip exactly", set(r) == set(odd) and all(r[s]["source"] == f"/p/{s}.png" for s in odd), str(sorted(r)))
check("odd stems: 'files' column for a stem with a space is ambiguous (split on ' ' gives 4 tokens)", len(r["space stem"]["files"].split(" ")) == 4, repr(r["space stem"]["files"]))
# 7b. done-flag resume for odd stems through build_workspace
root = os.path.join(D, "ws_odd"); shutil.rmtree(os.path.join(root, "vidi_output"), ignore_errors=True)
imgs, _ = W.probe_workspace(root)
ws = W.build_workspace(root, "image", imgs)
for it in ws.items[:3]: W.write_manifest_row(ws.manifest_path, row(it.stem, source=it.path))
ws2 = W.build_workspace(root, "image", imgs)
check("odd stems: done flags resume (3 of 5)", [it.done for it in ws2.items] == [True,True,True,False,False], str([(it.stem,it.done) for it in ws2.items]))

# 8. 5000-row rewrite time
m = os.path.join(T, "big", "manifest.csv"); os.makedirs(os.path.dirname(m))
with open(m, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=W.MANIFEST_FIELDS); w.writeheader()
    for i in range(5000): w.writerow(row(f"case_{i:05d}", source=f"/data/study/case_{i:05d}/img.dcm", files=f"png/case_{i:05d}_mask.png png/case_{i:05d}_roi.png png/case_{i:05d}_roi_mask.png"))
ts = []
for k in range(5):
    t0 = time.perf_counter(); W.write_manifest_row(m, row(f"new_{k}")); ts.append(time.perf_counter() - t0)
t5k = min(ts); sz = os.path.getsize(m)
t0 = time.perf_counter(); r = W.read_manifest(m); tr = time.perf_counter() - t0
check(f"5000-row manifest: write_manifest_row {t5k*1000:.1f} ms (read {tr*1000:.1f} ms, {sz/1e6:.2f} MB) → ~{t5k*4*1000:.0f} ms est. at 20k", t5k < 1.0, f"all={[round(t*1000,1) for t in ts]}")
# 20k real
with open(m, "a", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=W.MANIFEST_FIELDS)
    for i in range(5000, 20000): w.writerow(row(f"case_{i:05d}", source=f"/data/study/case_{i:05d}/img.dcm", files=f"png/case_{i:05d}_mask.png png/case_{i:05d}_roi.png"))
t0 = time.perf_counter(); W.write_manifest_row(m, row("new_x")); t20k = time.perf_counter() - t0
check(f"20000-row manifest: write_manifest_row {t20k*1000:.1f} ms", t20k < 2.0)

# 9. leftover manifest.csv.tmp from a crash
m = mk("tmpleft", GOOD); open(m + ".tmp", "w").write("garbage,partial\r\nxx")
r2, e2 = try_call(W.write_manifest_row, m, row("c"))
check("leftover manifest.csv.tmp: write ok, tmp consumed, rows a,b,c", e2 is None and not os.path.exists(m+".tmp") and set(W.read_manifest(m))=={"a","b","c"}, f"{e2!r}")
# 9b. leftover .tmp is a directory
m = mk("tmpdir", GOOD); os.makedirs(m + ".tmp")
r2, e2 = try_call(W.write_manifest_row, m, row("c"))
check("manifest.csv.tmp is a directory: write RAISES", e2 is not None, f"{type(e2).__name__ if e2 else None}: {e2}")

# 10. manifest.csv is a directory
p = os.path.join(T, "mandir"); os.makedirs(os.path.join(p, "manifest.csv"))
r, e = try_call(W.read_manifest, os.path.join(p, "manifest.csv"))
r2, e2 = try_call(W.write_manifest_row, os.path.join(p, "manifest.csv"), row("c"))
check("manifest.csv is a dir: read {} ; write RAISES", e is None and r == {} and e2 is not None, f"{type(e2).__name__ if e2 else None}: {e2}")

# 11. out dir read-only after it exists → write_manifest_row raises
p = os.path.join(T, "ro"); m = os.path.join(p, "manifest.csv"); W.write_manifest_row(m, row("a"))
os.chmod(p, 0o500)
try:
    r2, e2 = try_call(W.write_manifest_row, m, row("c"))
finally:
    os.chmod(p, 0o700)
check("read-only out dir: write_manifest_row RAISES", e2 is not None, f"{type(e2).__name__ if e2 else None}: {e2}")

# 12. two processes alternately saving into the same manifest (read-modify-write)
p = os.path.join(T, "two"); m = os.path.join(p, "manifest.csv")
code = f"""
import sys; sys.path.insert(0, {H.__file__.rsplit('/',1)[0]!r}); import harness as H; H.register_package()
from viewer_vidi import workspace as W
tag, n = sys.argv[1], int(sys.argv[2])
for i in range(n):
    W.write_manifest_row({m!r}, dict(stem=f"{{tag}}_{{i}}", source="s", saved_at="t", mask_pixels=1, x0="", y0="", x1="", y1="", formats="png", files="f"))
"""
for i in range(10):
    for tag in ("A", "B"):
        subprocess.run([H.PYTHON, "-c", code, tag + str(i), "1"], check=True, cwd="/tmp")
r = W.read_manifest(m)
check("two instances alternating: all 20 rows present", len(r) == 20, str(len(r)))
# concurrent burst
shutil.rmtree(p); os.makedirs(p)
procs = [subprocess.Popen([H.PYTHON, "-c", code, tag, "50"], cwd="/tmp") for tag in ("A","B","C")]
for pr in procs: pr.wait()
r = W.read_manifest(m)
check("three instances concurrently 50 rows each: rows kept", len(r) == 150, f"{len(r)}/150 — lost {150-len(r)} (read-modify-write race, exit codes {[pr.returncode for pr in procs]})")


# 13. stem stability: duplicate basenames change stems when a file is added/removed → done flags migrate to the wrong file
from PIL import Image
import numpy as np
root = os.path.join(T, "stemshift"); os.makedirs(os.path.join(root, "sub"))
for p_ in ("a.png", "sub/a.png", "b.png"):
    Image.fromarray(np.full((8, 8), 100, np.uint8), "L").save(os.path.join(root, p_))
imgs, _ = W.probe_workspace(root); ws = W.build_workspace(root, "image", imgs)
st = {os.path.relpath(it.path, root): it.stem for it in ws.items}
check("dup basenames: stems a / sub__a / b", st == {"a.png": "a", "sub/a.png": "sub__a", "b.png": "b"}, str(st))
# annotate ONLY root a.png
W.write_manifest_row(ws.manifest_path, row("a", source=os.path.join(root, "a.png")))
os.remove(os.path.join(root, "a.png"))
imgs, _ = W.probe_workspace(root); ws2 = W.build_workspace(root, "image", imgs)
flags = {os.path.relpath(it.path, root): (it.stem, it.done) for it in ws2.items}
check("after deleting the annotated root a.png, the NEVER-annotated sub/a.png is marked done (stem 'a' inherited)",
      flags.get("sub/a.png") == ("a", True), str(flags))
# reverse: annotate sub/a.png alone (stem 'a'), then add a root a.png → sub/a.png reverts to pending, new file is 'done'
root = os.path.join(T, "stemshift2"); os.makedirs(os.path.join(root, "sub"))
Image.fromarray(np.full((8, 8), 100, np.uint8), "L").save(os.path.join(root, "sub/a.png"))
imgs, _ = W.probe_workspace(root); ws = W.build_workspace(root, "image", imgs)
W.write_manifest_row(ws.manifest_path, row(ws.items[0].stem, source=ws.items[0].path))
Image.fromarray(np.full((8, 8), 100, np.uint8), "L").save(os.path.join(root, "a.png"))
imgs, _ = W.probe_workspace(root); ws2 = W.build_workspace(root, "image", imgs)
flags = {os.path.relpath(it.path, root): (it.stem, it.done) for it in ws2.items}
check("adding root a.png: annotated sub/a.png → pending as 'sub__a'; new a.png → done", flags == {"a.png": ("a", True), "sub/a.png": ("sub__a", False)}, str(flags))

# 14. out dir name "." → outputs land in the workspace root and get re-scanned as items on reopen
root = os.path.join(T, "dotout"); os.makedirs(root)
Image.fromarray(np.full((8, 8), 100, np.uint8), "L").save(os.path.join(root, "a.png"))
from viewer_vidi.annotation_export import ExportInput, ExportOptions, export_item
ws = W.build_workspace(root, "image", W.probe_workspace(root, ".")[0], ".")
px = np.full((8, 8), 100, np.float32); mk_ = np.zeros((8, 8), np.uint8); mk_[2:4, 2:4] = 1
written = export_item(ws.out_dir, ExportInput(stem="a", pixels=px, wc=100, ww=200, mask=mk_), ExportOptions(formats=("png",)))
W.write_manifest_row(ws.manifest_path, row("a", source=os.path.join(root, "a.png"), files=" ".join(written)))
imgs2, lists2 = W.probe_workspace(root, ".")
check("out dir '.': reopen scans the exported png/a_mask.png as a new item", [os.path.relpath(p, root) for p in imgs2] == ["a.png"], f"items={[os.path.relpath(p, root) for p in imgs2]} lists={lists2}")

n_fail = sum(1 for _, ok in res if not ok)
print(f"\n{len(res)-n_fail}/{len(res)} checks passed")
