"""Build synthetic fixtures for the perf lens (all under perf/fix)."""
import os, time, sys
import numpy as np
from PIL import Image

FIX = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/perf/fix"
BIG = os.path.join(FIX, "big"); os.makedirs(BIG, exist_ok=True)

def synth(n, bits):
    yy, xx = np.mgrid[0:n, 0:n]
    base = (np.sin(xx / 97.0) * np.cos(yy / 131.0) + 1.0) * 0.5
    rng = np.random.default_rng(0)
    noise = rng.random((n, n), dtype=np.float32) * 0.05
    v = np.clip(base + noise, 0, 1)
    if bits == 8:
        return (v * 255).astype(np.uint8)
    return (v * 65535).astype(np.uint16)

for n in (4096, 8192):
    for bits in (8, 16):
        p = os.path.join(BIG, f"png{n}_{bits}.png")
        if os.path.exists(p):
            print("exists", p); continue
        t0 = time.perf_counter()
        arr = synth(n, bits)
        im = Image.fromarray(arr)
        im.save(p, compress_level=1)
        print(f"wrote {p} mode={im.mode} {os.path.getsize(p)/1e6:.1f} MB in {time.perf_counter()-t0:.1f}s")

# 3000 tiny PNGs, 30 subdirs x 100
TINY = os.path.join(FIX, "tiny3000")
if not os.path.isdir(TINY):
    os.makedirs(TINY)
    tiny = Image.fromarray((np.arange(64, dtype=np.uint8).reshape(8, 8)))
    for d in range(30):
        sub = os.path.join(TINY, f"sub{d:02d}"); os.makedirs(sub)
        for i in range(100):
            tiny.save(os.path.join(sub, f"img_{d:02d}_{i:03d}.png"))
    print("wrote 3000 tiny PNGs")

# 20k-entry list files (txt + csv) over the tiny PNGs (duplicates -> unique_stems work)
tiny_files = sorted(os.path.join(dp, f) for dp, _, fs in os.walk(TINY) for f in fs)
LST = os.path.join(FIX, "list20k.txt")
with open(LST, "w") as f:
    f.write("# perf list\n")
    for i in range(20000):
        f.write(tiny_files[i % len(tiny_files)] + "\n")
CSV = os.path.join(FIX, "list20k.csv")
with open(CSV, "w") as f:
    f.write("id,path,label\n")
    for i in range(20000):
        f.write(f'{i},"{tiny_files[i % len(tiny_files)]}",{i % 3}\n')
print("wrote list20k.txt / .csv")

# 40-load alternating list (list mode: arbitrary absolute paths allowed)
CR  = "/media/zsk/ressd/research/alldata_backup/dicom/original"
crs = sorted(os.path.join(CR, f) for f in os.listdir(CR) if f.endswith(".dcm"))
NII = "/media/zsk/ressd/research/alldata_backup/Tongyu_Wang/radiology_qingyi/qingyi/+C/2035104/C.nii"
PNG = "/media/zsk/ressd/research/alldata_backup/project_workstation/PhD/image_exsample/3.png"
cycle = [crs[0], NII, PNG, os.path.join(BIG, "png4096_8.png"), crs[1], NII, PNG, os.path.join(BIG, "png4096_16.png")]
with open(os.path.join(FIX, "list40.txt"), "w") as f:
    for i in range(40):
        f.write(cycle[i % len(cycle)] + "\n")
print("wrote list40.txt")
