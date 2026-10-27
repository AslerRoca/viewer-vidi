"""Flow 7: Save & Next on the last item → status set, no advance, mask stays; re-save does not duplicate."""
import os, sys, shutil
import e2e_common as C
from e2e_common import check, H

ROOT = os.path.join(C.FX, "ws_last")
OUT = os.path.join(ROOT, "vidi_output")
shutil.rmtree(OUT, ignore_errors=True)
app, win = H.boot()
dock, quad = win._dock, win._quad
C.click_button(app, win._ws_btn)
cell = quad.active_cell(); canvas = cell.canvas()
C.open_dir_via_ui(app, win, ROOT)
ws = dock.workspace()
check("2 items, item 1 loaded", ws is not None and len(ws.items) == 2 and H.wait_loaded(app, cell))
C.click_button(app, dock._next_btn)
check("Next → last item, Next disabled", H.wait_loaded(app, cell) and dock._index == 1 and not dock._next_btn.isEnabled())
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.5, 0.3))
n = canvas.mask_pixels()
C.click_button(app, dock._save_next_btn); st = C.wait_status(app, dock)
check("Save & Next (button) on last: status Saved", st.startswith("Saved 1 file(s)"), st)
check("no advance: index stays 1, item ✓, count 2/2 · 1 done", dock._index == 1 and ws.items[1].done and dock._count_lbl.text() == "2/2 · 1 done", dock._count_lbl.text())
check("canvas not reloaded: mask kept", canvas.mask_pixels() == n and os.path.abspath(cell.series_data().meta.series_dir) == ws.items[1].path, str(canvas.mask_pixels()))
# Ctrl+S again on the same last item → re-save, manifest single row
C.ctrl_s(app, win, target=canvas); st = C.wait_status(app, dock)
rows = open(os.path.join(OUT, "manifest.csv")).read().splitlines()
check("Ctrl+S on last again: saved, still index 1, manifest 1 row", st.startswith("Saved") and dock._index == 1 and len(rows) == 2, f"{st} rows={len(rows)}")
# Prev → item 1, Ctrl+S with nothing drawn → nothing to save
C.click_button(app, dock._prev_btn); H.wait_loaded(app, cell)
C.ctrl_s(app, win, target=canvas); st = C.wait_status(app, dock)
check("Ctrl+S with empty canvas: Nothing to save, stays on item 1", st.startswith("Nothing to save") and dock._index == 0 and not ws.items[0].done, st)
# Ctrl+S with no workspace at all (fresh window)
win2_app, win2 = H.boot()
C.click_button(app, win2._ws_btn)
C.ctrl_s(app, win2, target=win2)
check("Ctrl+S without workspace → 'Open a workspace first.'", win2._dock._status_lbl.text() == "Open a workspace first.", win2._dock._status_lbl.text())
win2.close()
sys.exit(C.finish(win, app))
