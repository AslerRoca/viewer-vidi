"""Minimal repro: a truncated DICOM (header intact, PixelData missing/short) or a multi-frame
DICOM displays as an all-zero image and Save silently exports that black image, marks the
item done and records it in manifest.csv. LoaderWorker._read_slice_from_ds swallows the
pixel-decode exception and returns np.zeros.

Run: QT_QPA_PLATFORM=offscreen timeout 300 ~/miniconda3/envs/viewer_vidi/bin/python repro_truncated_zero_export.py
"""
import os, sys, time, shutil
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
import numpy as np
from PIL import Image

GOOD = "/media/zsk/ressd/research/alldata_backup/dicom/original/bpd1_20100101_1.dcm"   # pixel data starts at byte 4540
D = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/loaderasync/fx/repro_trunc"
shutil.rmtree(D, ignore_errors=True); os.makedirs(D)
with open(GOOD, "rb") as f: head = f.read(2048)
with open(os.path.join(D, "trunc2k.dcm"), "wb") as f: f.write(head)

app, win = H.boot()
dock, cell = win._dock, win._quad.active_cell()
canvas = cell.canvas()
errs = []; cell._loader.load_error.connect(errs.append)
H.open_workspace(app, win, D)
px = canvas.displayed_pixels()
print("load_error emitted:", errs, "| displayed:", px.shape, "min/max", px.min(), px.max())
dock._fmt_chk["png"].setChecked(True); dock._image_chk.setChecked(True)
dock._save(advance=False); app.processEvents()
print("Save status:", repr(dock._status_lbl.text()), "| item done:", dock._ws.items[0].done)
p = os.path.join(D, "vidi_output", "png", "trunc2k_image.png")
if os.path.isfile(p):
    a = np.array(Image.open(p)); print("exported", p, "shape", a.shape, "unique values", np.unique(a))
print(open(os.path.join(D, "vidi_output", "manifest.csv")).read())
win.close()
