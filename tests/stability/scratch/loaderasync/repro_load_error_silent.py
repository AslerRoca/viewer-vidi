"""Minimal repro: an item whose load fails (garbage .dcm / 0-byte .png / chmod 000) leaves the
panel on the loading page, the dock status empty, and Save says 'Image still loading' forever.
LoaderWorker.load_error is emitted but ViewCell never connects it.

Run: QT_QPA_PLATFORM=offscreen timeout 300 ~/miniconda3/envs/viewer_vidi/bin/python repro_load_error_silent.py
"""
import os, sys, time, shutil
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H

D = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/loaderasync/fx/repro_err"
shutil.rmtree(D, ignore_errors=True); os.makedirs(D)
with open(os.path.join(D, "a_garbage.dcm"), "wb") as f: f.write(os.urandom(4096))
open(os.path.join(D, "b_empty.png"), "wb").close()

app, win = H.boot()
dock, cell = win._dock, win._quad.active_cell()
errs = []; cell._loader.load_error.connect(errs.append)
H.open_workspace(app, win, D)               # first item = a_garbage.dcm
t0 = time.time()
while cell._loader.isRunning() and time.time() - t0 < 10: app.processEvents(); time.sleep(0.01)
H.pump(app, 500)
print("loader emitted load_error:", errs)
print("dock status label:", repr(dock._status_lbl.text()), "| canvas stack page:", cell._canvas_stack.currentIndex(), "(1 = loading page)")
dock._save(advance=False); app.processEvents()
print("Save status after failed load:", repr(dock._status_lbl.text()))
time.sleep(2); H.pump(app, 200); dock._save(advance=False); app.processEvents()
print("Save status 2 s later:", repr(dock._status_lbl.text()))
win.close()
