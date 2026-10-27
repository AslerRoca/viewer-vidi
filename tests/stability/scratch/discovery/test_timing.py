"""probe_workspace timing: 2000 tiny PNGs, 2000 extensionless DICM files, 2000 extensionless non-DICM, ressd fixture tree."""
import os, sys, shutil, time
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
H.register_package()
from viewer_vidi import workspace as W
from PIL import Image
SCR = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/discovery"

def fresh(name):
    d = os.path.join(SCR, "ws_" + name); shutil.rmtree(d, ignore_errors=True); os.makedirs(d); return d

def timed(label, fn, n=3):
    best = None
    for _ in range(n):
        t0 = time.perf_counter(); r = fn(); dt = time.perf_counter() - t0
        best = dt if best is None else min(best, dt)
    print(f"{label}: best of {n} = {best*1000:.0f} ms", flush=True)
    return r, best

# (a) 2000 tiny PNGs across 20 subdirs
d = fresh("png2000")
im = Image.new("L", (4, 4), 7)
for i in range(2000):
    sub = os.path.join(d, f"p{i % 20:02d}"); os.makedirs(sub, exist_ok=True)
    im.save(os.path.join(sub, f"img_{i:04d}.png"))
(imgs, lists), dt = timed("probe 2000 PNG (/tmp)", lambda: W.probe_workspace(d))
print("  found", len(imgs), "lists", len(lists))
ws, dt2 = timed("build_workspace 2000 PNG", lambda: W.build_workspace(d, "image", imgs))
print("  items", len(ws.items), "unique stems", len(set(i.stem for i in ws.items)))
# 2000 PNG all with the SAME basename in 2000 subdirs -> unique_stems fallback path
d2 = fresh("png2000dup")
for i in range(2000):
    sub = os.path.join(d2, f"p{i:04d}"); os.makedirs(sub, exist_ok=True)
    im.save(os.path.join(sub, "img.png"))
(imgs2, _), _ = timed("probe 2000 dup-name PNG", lambda: W.probe_workspace(d2))
ws2, _ = timed("build_workspace 2000 dup-name PNG", lambda: W.build_workspace(d2, "image", imgs2))
print("  unique stems", len(set(i.stem for i in ws2.items)), "sample", ws2.items[0].stem, ws2.items[-1].stem)

# (b) 2000 extensionless files with DICM magic (one 132-byte read each)
d3 = fresh("extless2000")
blob = b"\0" * 128 + b"DICM" + b"\0" * 64
for i in range(2000):
    sub = os.path.join(d3, f"s{i % 10}"); os.makedirs(sub, exist_ok=True)
    with open(os.path.join(sub, f"{42228791 + i}"), "wb") as f: f.write(blob)
(imgs3, _), dt3 = timed("probe 2000 extensionless DICM (/tmp)", lambda: W.probe_workspace(d3))
print("  found", len(imgs3))

# (c) 2000 extensionless NON-dicom files (every one opened and rejected)
d4 = fresh("extless_junk2000")
for i in range(2000):
    with open(os.path.join(d4, f"junk{i}"), "wb") as f: f.write(b"x" * 200)
(imgs4, _), dt4 = timed("probe 2000 extensionless junk (/tmp)", lambda: W.probe_workspace(d4))
print("  found", len(imgs4))

# (d) 2000 .txt files at top level (find_list_files parses every one)
d5 = fresh("txt2000")
for i in range(2000):
    with open(os.path.join(d5, f"notes{i}.txt"), "w") as f: f.write("lorem ipsum\n" * 50)
(imgs5, lists5), dt5 = timed("probe 2000 .txt notes at top level (/tmp)", lambda: W.probe_workspace(d5), n=2)
print("  lists", len(lists5))

# (e) real exFAT USB fixture tree: 3713 files, mostly extensionless DICOM (read-only)
FIXT = "/media/zsk/ressd/research/alldata_backup/mymri/Liver_3T_sub5_2026_07_05"
t0 = time.perf_counter(); imgs6, lists6 = W.probe_workspace(FIXT); dt6 = time.perf_counter() - t0
print(f"probe ressd Liver_3T tree (3713 files, exFAT USB) first run: {dt6:.2f} s -> {len(imgs6)} images, {len(lists6)} lists", flush=True)
t0 = time.perf_counter(); imgs6b, _ = W.probe_workspace(FIXT); dt6b = time.perf_counter() - t0
print(f"  second run (warm cache): {dt6b:.2f} s", flush=True)
t0 = time.perf_counter(); ws6 = W.build_workspace(FIXT, "image", imgs6); dt6c = time.perf_counter() - t0
print(f"  build_workspace: {dt6c:.2f} s, {len(ws6.items)} items, {len(set(i.stem for i in ws6.items))} unique stems; sample stems {ws6.items[0].stem!r} {ws6.items[-1].stem!r}")
dicomdir_items = [i for i in ws6.items if "DICOMDIR" in i.path.upper()]
print("  DICOMDIR items:", [i.path for i in dicomdir_items])
