"""Re-saving an item with fewer formats / cleared mask: stale files stay on disk, manifest no longer lists them."""
from common import *
import numpy as np, glob
from viewer_vidi import workspace as W
app, win = H.boot(); dock, quad = win._dock, win._quad
d = fresh_ws("p06", [os.path.join(FIX, "bpd1_20100101_1.dcm")])
ws = H.open_workspace(app, win, d)
c = quad.active_cell().canvas()
H.drag(app, c, H.pt(c,0.3,0.3), H.pt(c,0.5,0.3))
dock._tool_btns["rect"].setChecked(True); dock._apply_tool()
H.drag(app, c, H.pt(c,0.2,0.2), H.pt(c,0.7,0.7))
for k in dock._fmt_chk.values(): k.setChecked(True)
dock._image_chk.setChecked(True)
dock._save(advance=False); app.processEvents()
out = ws.out_dir; stem = ws.items[0].stem
first = sorted(os.path.relpath(p, out) for p in glob.glob(os.path.join(out, "*", "*")))
print("after 1st save:", first)
check("first save wrote 12 files", len(first) == 12, str(len(first)))
# second save: only PNG, mask cleared (rect kept), no Original
dock._fmt_chk["jpeg"].setChecked(False); dock._fmt_chk["nifti"].setChecked(False); dock._image_chk.setChecked(False)
c.clear_annotations()     # drops rect too → re-draw the rect only
dock._tool_btns["rect"].setChecked(True); dock._apply_tool()
H.drag(app, c, H.pt(c,0.2,0.2), H.pt(c,0.7,0.7))
check("mask empty, rect set", c.mask_pixels() == 0 and c.crop_rect() is not None)
dock._save(advance=False); app.processEvents()
man = W.read_manifest(ws.manifest_path)[stem]
second = sorted(os.path.relpath(p, out) for p in glob.glob(os.path.join(out, "*", "*")))
print("manifest row:", man); print("on disk after 2nd save:", second)
listed = set(man["files"].split())
stale = [f for f in second if f not in listed]
check("manifest files == files on disk for this stem (no stale products)", not stale, f"stale on disk, not in manifest: {stale}")
check("manifest mask_pixels is 0 but png/<stem>_mask.png still exists from save 1", not (man["mask_pixels"] == "0" and os.path.isfile(os.path.join(out, "png", stem + "_mask.png"))), "stale mask file present")
win.close(); app.processEvents()
sys.exit(summary())
