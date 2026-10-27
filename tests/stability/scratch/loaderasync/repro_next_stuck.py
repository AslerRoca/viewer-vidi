"""Minimal repro: when the next item cannot be opened (file vanished / unrecognised after the
workspace was opened), AnnotationDock._load_index returns before updating self._index, so
Next (and Save & Next) stay on the same index forever instead of skipping the item.

Run: QT_QPA_PLATFORM=offscreen timeout 300 ~/miniconda3/envs/viewer_vidi/bin/python repro_next_stuck.py
"""
import os, sys, shutil
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H

SRC = "/media/zsk/ressd/research/alldata_backup/dicom/original/bpd1_20100101_1.dcm"
D = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/loaderasync/fx/repro_stuck"
shutil.rmtree(D, ignore_errors=True); os.makedirs(D)
for n in ("a.dcm", "b.dcm", "c.dcm"): shutil.copy(SRC, os.path.join(D, n))

app, win = H.boot()
dock, cell = win._dock, win._quad.active_cell()
H.open_workspace(app, win, D)                 # item 0 = a.dcm loaded
os.remove(os.path.join(D, "b.dcm"))           # item 1 vanishes (e.g. moved by another process)
for k in range(3):
    dock._step(+1); H.pump(app, 100)
    print(f"Next #{k+1}: index={dock._index} next_enabled={dock._next_btn.isEnabled()} status={dock._status_lbl.text()!r}")
win.close()
