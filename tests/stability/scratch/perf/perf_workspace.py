"""Perf lens, no Qt: workspace.py (scan / parse / build / manifest) timings."""
import os, sys, time, shutil, json
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
H.register_package()
from viewer_vidi import workspace as W

FIX = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/perf/fix"
MR  = "/media/zsk/ressd/research/alldata_backup/mymri/Liver_3T_sub5_2026_07_05/DICOM/26070517/54450002"
def rss():
    with open("/proc/self/status") as f:
        for ln in f:
            if ln.startswith("VmRSS"): return int(ln.split()[1]) / 1024
R = {}
def t(name, fn, reps=1):
    best = None; out = None
    for _ in range(reps):
        t0 = time.perf_counter(); out = fn(); dt = time.perf_counter() - t0
        best = dt if best is None else min(best, dt)
    R[name] = round(best, 4); print(f"{name}: {best*1000:.1f} ms"); return out

# warm the page cache first (fixtures were just written, but be fair)
tiny = os.path.join(FIX, "tiny3000")
imgs = t("scan_images tiny3000 (cold-ish)", lambda: W.scan_images(tiny))
print("  found", len(imgs))
imgs = t("scan_images tiny3000 (warm, best of 3)", lambda: W.scan_images(tiny), reps=3)
pr = t("probe_workspace tiny3000 (warm, best of 3)", lambda: W.probe_workspace(tiny), reps=3)
print("  images", len(pr[0]), "lists", len(pr[1]))
# extensionless DICOM dir: is_dicom_file opens every file for the magic
mr = t("scan_images MR dir 500 extensionless DICOM (cold)", lambda: W.scan_images(MR))
print("  found", len(mr))
mr = t("scan_images MR dir 500 extensionless DICOM (warm, best of 3)", lambda: W.scan_images(MR), reps=3)

lst = t("parse_list_file list20k.txt (best of 3)", lambda: W.parse_list_file(os.path.join(FIX, "list20k.txt")), reps=3)
print("  entries", len(lst))
lstc = t("parse_list_file list20k.csv (best of 3)", lambda: W.parse_list_file(os.path.join(FIX, "list20k.csv")), reps=3)
print("  entries", len(lstc), "sample", lstc[0])
r0 = rss()
ws = t("build_workspace 20k list entries (3000 unique files, dup stems) best of 3",
       lambda: W.build_workspace(FIX, "list", lst), reps=3)
print("  items", len(ws.items), "missing", len(ws.missing), "unique stems", len({i.stem for i in ws.items}), "RSS delta MB", round(rss() - r0, 1))
print("  sample stems", [i.stem for i in ws.items[:2]], [i.stem for i in ws.items[3000:3002]])
# find_list_files on the FIX root: parses list20k.txt + .csv fully (40k resolves) just to decide usability
fl = t("find_list_files FIX root (2 x 20k-entry lists)", lambda: W.find_list_files(FIX), reps=3)
print("  lists", [os.path.basename(p) for p in fl])
pw = t("probe_workspace FIX root (tiny3000 + big + 20k lists) — what _open_dir blocks on", lambda: W.probe_workspace(FIX), reps=1)
print("  images", len(pw[0]), "lists", len(pw[1]))

# manifest growth: write_manifest_row re-reads and rewrites the whole file every save
md = os.path.join(FIX, "manifest_perf"); shutil.rmtree(md, ignore_errors=True); os.makedirs(md)
mp = os.path.join(md, "manifest.csv")
times = []
t0all = time.perf_counter()
for i in range(5000):
    row = dict(stem=f"item_{i:05d}", source=f"/data/x/item_{i:05d}.dcm", saved_at="2026-10-26T20:00:00",
               mask_pixels=i, x0=1, y0=2, x1=300, y1=400, formats="png jpeg nifti",
               files=" ".join(f"{f}/item_{i:05d}_{s}.{f}" for f in ("png","jpeg","nifti") for s in ("image","mask","roi","roi_mask")))
    t0 = time.perf_counter(); W.write_manifest_row(mp, row); times.append(time.perf_counter() - t0)
tot = time.perf_counter() - t0all
R["manifest 5000 rows total s"] = round(tot, 3)
R["manifest save #1 ms"] = round(times[0]*1000, 2)
R["manifest save #1000 ms"] = round(times[999]*1000, 2)
R["manifest save #5000 ms"] = round(times[-1]*1000, 2)
R["manifest file MB"] = round(os.path.getsize(mp)/1e6, 2)
print(f"write_manifest_row: 5000 sequential saves total {tot:.2f}s; #1 {times[0]*1000:.2f} ms, #1000 {times[999]*1000:.2f} ms, #5000 {times[-1]*1000:.2f} ms; file {os.path.getsize(mp)/1e6:.2f} MB")
rm = t("read_manifest 5000 rows (best of 3)", lambda: W.read_manifest(mp), reps=3)
print("  rows", len(rm))
# re-saving an existing stem (what Save does for a redo) at 5000 rows
t("write_manifest_row replace existing @5000 rows", lambda: W.write_manifest_row(mp, dict(stem="item_02500", source="s", saved_at="t", mask_pixels=1)), reps=3)
print(json.dumps(R, indent=1))
