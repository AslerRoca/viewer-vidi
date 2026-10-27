"""Minimal repro: stale headers_ready/pixels_ready from a cancelled load are delivered
after load_meta() of the next item, and Save in that window writes the PREVIOUS
item's pixels under the CURRENT item's stem (and marks it done).

Run:  QT_QPA_PLATFORM=offscreen timeout 300 ~/miniconda3/envs/viewer_vidi/bin/python repro_stale_loader_save.py
"""
import os, sys, time, shutil
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
import numpy as np
from PIL import Image

FX = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/loaderasync/fx/rapid"
app, win = H.boot()
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
shutil.rmtree(os.path.join(FX, "vidi_output"), ignore_errors=True)
ws = H.open_workspace(app, win, FX)            # item 0 = bpd1_20100101_1 (2044x1514)
iA = next(i for i, it in enumerate(ws.items) if it.stem == "bpd1_20100102_1")   # 2570x2040
iB = 0
dock._fmt_chk["png"].setChecked(True); dock._image_chk.setChecked(True)

dock._load_index(iA)            # start loading A
cell._loader.wait()             # main thread busy until A's thread is done: both A signals are now queued
dock._load_index(iB)            # user clicks item B: load_meta(B) resets sd/pixels and starts B

# the queued A signals arrive now, then B's headers_ready; B's pixels come later
t0 = time.time(); hit = False
while time.time() - t0 < 15:
    app.processEvents()
    sd, px = cell.series_data(), canvas.displayed_pixels()
    if sd is not None and sd.meta.series_dir == ws.items[iB].path and px is not None and px.shape == (2570, 2040):
        hit = True
        print("WINDOW: sd =", os.path.basename(sd.meta.series_dir), "but displayed pixels shape =", px.shape)
        dock._save(advance=False)
        print("Save status:", dock._status_lbl.text(), "| item done:", ws.items[iB].done)
        break
    time.sleep(0.0005)
H.wait_loaded(app, cell)
out = os.path.join(FX, "vidi_output", "png", f"{ws.items[iB].stem}_image.png")
if os.path.isfile(out):
    print("written", out, "shape", np.array(Image.open(out)).shape, "(item B is 2044x1514 -> WRONG if 2570x2040)")
print("window observed:", hit)
win.close()
