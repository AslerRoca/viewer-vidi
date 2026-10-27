"""A manifest.csv with a user-added column: Save button → write_manifest_row ValueError inside a Qt slot."""
import os, sys, shutil, csv
from common import *
import harness as H
H.register_package()
from viewer_vidi import workspace as W
app, win = H.boot()
D = os.path.join(SCR, "data", "ws_abort"); shutil.rmtree(D, ignore_errors=True); os.makedirs(D)
for f in sorted(os.listdir(FIX))[:2]: shutil.copy(os.path.join(FIX, f), D)
outd = os.path.join(D, "vidi_output"); os.makedirs(outd)
with open(os.path.join(outd, "manifest.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(list(W.MANIFEST_FIELDS) + ["notes"])
    w.writerow(["zzz_not_an_item", "src", "t", "3", "1", "2", "3", "4", "png", "png/x.png", "reviewed by me"])
ws = H.open_workspace(app, win, D)
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.5, 0.2))
check("stroke painted", canvas.mask_pixels() > 0)
print("clicking Save…", flush=True)
dock._save_btn.click()          # goes through the Qt slot → unhandled exception
app.processEvents()
print("still alive after Save; png dir:", sorted(os.listdir(os.path.join(outd, "png"))) if os.path.isdir(os.path.join(outd, "png")) else None,
      "manifest rows:", sorted(W.read_manifest(ws.manifest_path)), "tmp exists:", os.path.exists(ws.manifest_path + ".tmp"), flush=True)
check("Save with an extra manifest column does not crash", True)
win.close(); app.processEvents()
sys.exit(summary())
