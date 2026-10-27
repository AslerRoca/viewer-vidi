"""What a truncated .dcm and a DICOMDIR.dcm item do when the dock loads them."""
import os, sys, shutil, time
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
app, win = H.boot()
import numpy as np
from viewer_vidi import workspace as W
SCR = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/discovery"
FIX_DCM = "/media/zsk/ressd/research/alldata_backup/dicom/original"
FIX_DICOMDIR = "/media/zsk/ressd/research/alldata_backup/mymri/Liver_3T_sub5_2026_07_05/DICOMDIR"
d = os.path.join(SCR, "gws_badload"); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
src = open(os.path.join(FIX_DCM, "bpd1_20100101_1.dcm"), "rb").read()
open(os.path.join(d, "a_trunc4k.dcm"), "wb").write(src[:4000])
open(os.path.join(d, "b_trunc_half.dcm"), "wb").write(src[:len(src)//2])
shutil.copy(FIX_DICOMDIR, os.path.join(d, "c_DICOMDIR.dcm"))
dock, quad = win._dock, win._quad
win._ws_btn.setChecked(True); app.processEvents()
cell = quad.active_cell(); canvas = cell.canvas()
imgs, _ = W.probe_workspace(d); ws = W.build_workspace(d, "image", imgs)
dock._out_edit.setText("vidi_output"); dock._set_workspace(ws)
for i in range(3):
    dock._load_index(i); t0 = time.perf_counter()
    ok = H.wait_loaded(app, cell, timeout=15.0); dt = time.perf_counter() - t0
    px = canvas.displayed_pixels()
    print(f"{ws.items[i].stem}: loaded={ok} in {dt:.2f}s shape={None if px is None else px.shape} "
          f"min/max={None if px is None else (float(px.min()), float(px.max()))} status={dock._status_lbl.text()!r} "
          f"label={cell._series_lbl.text()!r}", flush=True)
    if ok:
        dock._image_chk.setChecked(True); dock._save(advance=False); H.pump(app, 200)
        print("   save ->", dock._status_lbl.text())
win.close(); app.processEvents()
