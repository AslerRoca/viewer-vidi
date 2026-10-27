"""loaderasync T5: realistic ordering — Next/Prev clicks are POSTED through the event loop
(QTimer) at random 1-30 ms gaps while loads run, and at every loop turn we check whether the
cell ever holds sd of one file while displaying pixels of another shape."""
import os, sys, time, shutil, random
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
import numpy as np
import pydicom
from PyQt5.QtCore import QTimer

FX = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/loaderasync/fx"
root = os.path.join(FX, "rapid")
shape_of = {}
for f in sorted(os.listdir(root)):
    if f.endswith(".dcm"):
        ds = pydicom.dcmread(os.path.join(root, f), stop_before_pixels=True)
        shape_of[os.path.join(root, f)] = (int(ds.Rows), int(ds.Columns))
print("INFO shapes:", {os.path.basename(k): v for k, v in shape_of.items()})

app, win = H.boot()
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
shutil.rmtree(os.path.join(root, "vidi_output"), ignore_errors=True)
ws = H.open_workspace(app, win, root)

random.seed(7)
N = int([a for a in sys.argv[1:] if a.isdigit()][0]) if any(a.isdigit() for a in sys.argv[1:]) else 300
mismatches = []
SAVE_ON_MISMATCH = '--save' in sys.argv
saved_in_window = []
stale_sd = []
clicks = [0]
def click():
    btn = dock._next_btn if dock._next_btn.isEnabled() and random.random() < 0.6 else dock._prev_btn
    if not btn.isEnabled(): btn = dock._next_btn
    btn.click(); clicks[0] += 1
    if clicks[0] < N:
        QTimer.singleShot(random.randint(1, 30), click)
QTimer.singleShot(1, click)
t0 = time.time()
while (clicks[0] < N or cell._loader.isRunning()) and time.time() - t0 < 240:
    app.processEvents()
    sd = cell.series_data(); px = canvas.displayed_pixels()
    cur = dock._ws.items[dock._index].path
    if sd is not None and os.path.abspath(sd.meta.series_dir) != os.path.abspath(cur):
        stale_sd.append((clicks[0], os.path.basename(sd.meta.series_dir), os.path.basename(cur)))
    if sd is not None and px is not None and px.shape != shape_of.get(sd.meta.series_dir):
        mismatches.append((clicks[0], os.path.basename(sd.meta.series_dir), px.shape))
        if SAVE_ON_MISMATCH and not saved_in_window:
            dock._fmt_chk["png"].setChecked(True); dock._image_chk.setChecked(True)
            dock._save(advance=False)
            saved_in_window.append((dock._ws.items[dock._index].stem, shape_of[dock._ws.items[dock._index].path], px.shape, dock._status_lbl.text()))
    time.sleep(0.0005)
H.wait_loaded(app, cell); H.pump(app, 300)
sd = cell.series_data(); px = canvas.displayed_pixels(); m = canvas.mask()
final_ok = (sd is not None and os.path.abspath(sd.meta.series_dir) == os.path.abspath(dock._ws.items[dock._index].path)
            and px is not None and m is not None and m.shape == px.shape == shape_of[sd.meta.series_dir])
print(f"clicks={clicks[0]} elapsed={time.time()-t0:.1f}s")
print("PASS" if final_ok else "FAIL", "T5 final state consistent", dict(sd=os.path.basename(sd.meta.series_dir) if sd else None, px=None if px is None else px.shape, idx=dock._index))
print("PASS" if not mismatches else "FAIL", f"T5 sd/pixels shape mismatch windows observed: {len(mismatches)}", mismatches[:5])
print("PASS" if not stale_sd else "FAIL", f"T5 stale sd (sd != current item) windows observed: {len(set(s[0] for s in stale_sd))} distinct clicks", stale_sd[:5])
if saved_in_window:
    from PIL import Image
    stem, expected_shape, px_shape, status = saved_in_window[0]
    f = os.path.join(root, "vidi_output", "png", f"{stem}_image.png")
    got = np.array(Image.open(f)).shape if os.path.isfile(f) else None
    print("FAIL" if got != expected_shape else "PASS", f"T5 Save inside the realistic mismatch window: item {stem} (true shape {expected_shape}) -> written {got}; status {status!r}")
win.close()
