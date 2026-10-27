"""Perf lens, no Qt: export_item of an 8192x8192 slice, all formats; time + sizes + RSS peak."""
import os, sys, time, shutil, json, threading
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
H.register_package()
import numpy as np
from viewer_vidi.annotation_export import ExportInput, ExportOptions, export_item, window_to_uint8

OUT = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/perf/fix/export8192"
shutil.rmtree(OUT, ignore_errors=True); os.makedirs(OUT)
def rss():
    with open("/proc/self/status") as f:
        for ln in f:
            if ln.startswith("VmRSS"): return int(ln.split()[1]) / 1024
peak = [0.0]; stop = [False]
def watch():
    while not stop[0]:
        peak[0] = max(peak[0], rss()); time.sleep(0.005)

n = 8192
yy, xx = np.mgrid[0:n, 0:n]
px = ((np.sin(xx / 97.0) * np.cos(yy / 131.0) + 1.0) * 2047.5).astype(np.float32); del yy, xx
mask = np.zeros((n, n), np.uint8); mask[1000:7000, 1500:6500] = 1
rect = (500, 600, 7900, 7700)
inp = ExportInput(stem="big", pixels=px, wc=2048, ww=4096, invert=True, mask=mask, rect=rect, spacing=(0.1, 0.1))
R = {}
base = rss(); print(f"RSS before export {base:.0f} MB (pixels 256 MB + mask 64 MB held)")
th = threading.Thread(target=watch, daemon=True); th.start()
for fmt in ("png", "jpeg", "nifti"):
    peak[0] = rss()
    t0 = time.perf_counter()
    w = export_item(OUT, inp, ExportOptions(formats=(fmt,), save_image=True))
    dt = time.perf_counter() - t0
    sizes = {os.path.basename(p): round(os.path.getsize(os.path.join(OUT, p))/1e6, 1) for p in w}
    R[fmt] = dict(seconds=round(dt, 2), peak_rss_delta_MB=round(peak[0] - base, 0), files_MB=sizes)
    print(f"{fmt}: {dt:.2f}s, peak RSS delta {peak[0]-base:.0f} MB, files MB {sizes}")
peak[0] = rss(); t0 = time.perf_counter()
w = export_item(OUT, inp, ExportOptions(formats=("png", "jpeg", "nifti"), save_image=True))
dt = time.perf_counter() - t0
R["all3"] = dict(seconds=round(dt, 2), peak_rss_delta_MB=round(peak[0] - base, 0), n_files=len(w))
print(f"all three formats, 4 products each: {dt:.2f}s, {len(w)} files, peak RSS delta {peak[0]-base:.0f} MB")
stop[0] = True
t0 = time.perf_counter(); u8 = window_to_uint8(px, 2048, 4096, True); R["window_to_uint8_8192_s"] = round(time.perf_counter() - t0, 3)
print(f"window_to_uint8 alone at 8192²: {R['window_to_uint8_8192_s']*1000:.0f} ms")
# verify the invert/window actually landed in the file
from PIL import Image
im = np.array(Image.open(os.path.join(OUT, "png", "big_image.png")))
print("png image shape/dtype", im.shape, im.dtype, "equal to window_to_uint8:", np.array_equal(im, u8))
print(json.dumps(R, indent=1))
