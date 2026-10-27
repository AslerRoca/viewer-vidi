"""Repro: an exception raised by write_manifest_row / read_manifest inside a Qt slot aborts the whole app.
Usage: QT_QPA_PLATFORM=offscreen timeout 300 python repro_abort_manifest_write.py {dir|ro|extracol|nonutf8|nul}
  dir      <out>/manifest.csv is a directory          → Save: IsADirectoryError in write_manifest_row (export already wrote png/)
  ro       out dir chmod 500 after png/ exists         → Save: PermissionError creating manifest.csv.tmp (png overwritten, manifest stale)
  extracol manifest has an extra 'note' column         → Save: ValueError from csv.DictWriter
  nonutf8  manifest holds a latin-1 byte               → Open directory: UnicodeDecodeError in build_workspace → read_manifest
  nul      manifest has a NUL-filled tail              → Open directory: _csv.Error 'line contains NUL'
Expected: an error dialog and the app keeps running. Observed: traceback on stderr + SIGABRT (rc 134), 'ALIVE' never printed."""
import os, sys, shutil
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB); import harness as H
import numpy as np; from PIL import Image
variant = sys.argv[1]
root = os.path.join(STAB, "manifest", "work", "repro_" + variant); out = os.path.join(root, "vidi_output")
if os.path.isdir(out): os.chmod(out, 0o700)
shutil.rmtree(root, ignore_errors=True); os.makedirs(out)
Image.fromarray(np.full((60, 80), 120, np.uint8), "L").save(os.path.join(root, "a.png"))
man = os.path.join(out, "manifest.csv"); HDR = "stem,source,saved_at,mask_pixels,x0,y0,x1,y1,formats,files"
if variant == "dir": os.makedirs(man)
elif variant == "extracol": open(man, "w", newline="").write(HDR + ",note\r\nzz,/x,t,1,,,,,png,png/zz_mask.png,hi\r\n")
elif variant == "nonutf8": open(man, "wb").write((HDR + "\r\n").encode() + b"\xe4,/x,t,1,,,,,png,f\r\n")
elif variant == "nul": open(man, "wb").write((HDR + "\r\n").encode() + b"\x00" * 64)
app, win = H.boot(); dock = win._dock
from viewer_vidi import annotation_dock as AD
AD.QFileDialog = type("FD", (), {"getExistingDirectory": staticmethod(lambda *a, **k: root)})
win._ws_btn.setChecked(True); app.processEvents()
print("clicking Open directory…", flush=True)
dock._open_dir_btn.click(); app.processEvents()                 # nonutf8 / nul abort here
cell = win._quad.active_cell(); H.wait_loaded(app, cell); canvas = cell.canvas()
H.drag(app, canvas, H.pt(canvas, .3, .3), H.pt(canvas, .6, .3))
if variant == "ro": os.makedirs(os.path.join(out, "png")); os.chmod(out, 0o500)
H.auto_close_dialogs(app, 300)
print("clicking Save…", flush=True)
try:
    dock._save_btn.click(); H.pump(app, 300)                      # dir / ro / extracol abort here
finally:
    if variant == "ro": os.chmod(out, 0o700)
print("ALIVE after save; out dir now holds:", sorted(os.listdir(out)), "done =", dock._ws.items[0].done, flush=True)
