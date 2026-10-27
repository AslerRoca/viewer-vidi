"""Output dir not writable for new files (but png/ subdir is): Save writes the PNG, then the manifest
rewrite raises PermissionError inside the Save slot."""
import os, sys, shutil, stat
from common import *
import harness as H
H.register_package()
from viewer_vidi import workspace as W
app, win = H.boot()
D = os.path.join(SCR, "data", "ws_perm"); shutil.rmtree(D, ignore_errors=True); os.makedirs(D)
for f in sorted(os.listdir(FIX))[:2]: shutil.copy(os.path.join(FIX, f), D)
outd = os.path.join(D, "vidi_output"); os.makedirs(os.path.join(outd, "png"))
os.chmod(outd, stat.S_IRUSR | stat.S_IXUSR)          # r-x: can enter, cannot create manifest.csv.tmp
ws = H.open_workspace(app, win, D)
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.5, 0.2))
check("stroke painted", canvas.mask_pixels() > 0)
seen = H.auto_close_dialogs(app, 300)
print("clicking Save…", flush=True)
dock._save_btn.click(); app.processEvents(); H.pump(app, 400)
print("still alive; png dir:", sorted(os.listdir(os.path.join(outd, "png"))), "dialogs:", seen, "status:", dock._status_lbl.text(), flush=True)
check("Save with unwritable out dir reports an error instead of crashing", bool(seen))
os.chmod(outd, stat.S_IRWXU)
win.close(); app.processEvents()
sys.exit(summary())
