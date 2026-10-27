"""Re-saving an item after the rectangle was cleared (or a format unticked) leaves the
earlier <stem>_roi* / jpeg files on disk although the manifest row no longer lists them."""
from common import *
from viewer_vidi import workspace as W
app, win = H.boot(); dock, quad = win._dock, win._quad
root = fresh_ws("stale")
ws = H.open_workspace(app, win, root, "image")
cell = quad.active_cell(); canvas = cell.canvas()
dock._fmt_chk["png"].setChecked(True); dock._fmt_chk["jpeg"].setChecked(True); dock._fmt_chk["nifti"].setChecked(False)
dock._tool_btns["rect"].click(); H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.6, 0.6))
dock._tool_btns["paint"].click(); H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.5, 0.3))
stem = ws.items[0].stem
dock._save(advance=False); app.processEvents()
row1 = W.read_manifest(ws.manifest_path)[stem]
print("save 1:", dock._status_lbl.text()); print("  manifest files:", row1["files"])
# second save: no rectangle, PNG only
dock._clear_btn.click(); H.drag(app, canvas, H.pt(canvas, 0.3, 0.5), H.pt(canvas, 0.5, 0.5))
dock._fmt_chk["jpeg"].setChecked(False)
dock._save(advance=False); app.processEvents()
row2 = W.read_manifest(ws.manifest_path)[stem]
print("save 2:", dock._status_lbl.text()); print("  manifest files:", row2["files"])
on_disk = sorted(os.path.relpath(os.path.join(dp, f), ws.out_dir) for dp, _, fs in os.walk(ws.out_dir) for f in fs if f.startswith(stem))
listed = set(row2["files"].split())
stale = [f for f in on_disk if f not in listed]
print("  files on disk for stem:", on_disk)
print("  on disk but NOT in the manifest row:", stale)
ok = not stale
print("RESULT:", "PASS" if ok else "FAIL (stale products from the previous save remain next to the manifest)")
win.close(); app.processEvents(); sys.exit(0 if ok else 1)
