"""Flow 5: close and reopen the same image-mode workspace (separate processes) →
✓ flags restored from manifest.csv and the first pending item selected.
argv[1]: 'phase1' (annotate+save items 1,2 of 3, leave 3) | 'phase2' (reopen, verify)
         | 'mid1' (save only item 2) | 'mid2' (reopen: first pending = item 1)
         | 'nomanifest' (reopen after deleting manifest.csv: all pending)"""
import os, sys, shutil
import e2e_common as C
from e2e_common import check, H
import numpy as np

phase = sys.argv[1]
ROOT = os.path.join(C.FX, "ws_reopen")
OUT = os.path.join(ROOT, "vidi_output")
if phase in ("phase1", "mid1"):
    shutil.rmtree(OUT, ignore_errors=True)
if phase == "nomanifest":
    os.remove(os.path.join(OUT, "manifest.csv"))

app, win = H.boot()
dock, quad = win._dock, win._quad
C.click_button(app, win._ws_btn)
cell = quad.active_cell(); canvas = cell.canvas()
seen = C.open_dir_via_ui(app, win, ROOT)
check("no dialog", seen == [], str(seen))
ws = dock.workspace()
check("3 items", ws is not None and len(ws.items) == 3)
check("first pending loaded", H.wait_loaded(app, cell))

if phase == "phase1":
    check("fresh: all ○, index 0", C.list_texts(dock) == ["○ " + it.stem for it in ws.items] and dock._index == 0, str(C.list_texts(dock)))
    H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.5, 0.3))
    C.ctrl_s(app, win, target=canvas); st = C.wait_status(app, dock)
    check("item1 saved", st.startswith("Saved 1 file(s)"), st)
    check("advanced to item 2", H.wait_loaded(app, cell) and dock._index == 1 and canvas.mask_pixels() == 0)
    H.drag(app, canvas, H.pt(canvas, 0.3, 0.5), H.pt(canvas, 0.5, 0.5))
    C.ctrl_s(app, win, target=canvas); st = C.wait_status(app, dock)
    check("item2 saved", st.startswith("Saved 1 file(s)"), st)
    check("advanced to item 3 (pending, unsaved)", H.wait_loaded(app, cell) and dock._index == 2 and not ws.items[2].done)
    check("list ✓ ✓ ○", [t[0] for t in C.list_texts(dock)] == ["✓", "✓", "○"], str(C.list_texts(dock)))
    rows = open(os.path.join(OUT, "manifest.csv")).read().splitlines()
    check("manifest has header + 2 rows", len(rows) == 3, str(rows))
elif phase == "phase2":
    check("reopen: ✓ ✓ ○ restored", [t[0] for t in C.list_texts(dock)] == ["✓", "✓", "○"], str(C.list_texts(dock)))
    check("reopen: first pending (item 3) selected", dock._index == 2 and dock._list.currentRow() == 2, f"{dock._index} {dock._list.currentRow()}")
    check("reopen: item 3 shown in the active panel", os.path.abspath(cell.series_data().meta.series_dir) == ws.items[2].path)
    check("count label 3/3 · 2 done", dock._count_lbl.text() == "3/3 · 2 done", dock._count_lbl.text())
    check("ws label '3 items, 2 done'", "3 items, 2 done" in dock._ws_lbl.text(), dock._ws_lbl.text())
    check("Next disabled on last, Prev enabled", not dock._next_btn.isEnabled() and dock._prev_btn.isEnabled())
    check("status label empty after reopen", dock._status_lbl.text() == "")
    # re-save a done item: Prev → item 2 (done) → Save → manifest row replaced, not duplicated
    C.click_button(app, dock._prev_btn)
    check("Prev → item 2 loaded (done item shows no saved mask: documented)", H.wait_loaded(app, cell) and dock._index == 1 and canvas.mask_pixels() == 0)
    H.drag(app, canvas, H.pt(canvas, 0.6, 0.6), H.pt(canvas, 0.7, 0.6))
    C.click_button(app, dock._save_btn); st = C.wait_status(app, dock)
    check("re-save done item ok", st.startswith("Saved 1 file(s)"), st)
    rows = open(os.path.join(OUT, "manifest.csv")).read().splitlines()
    check("manifest still header + 2 rows (row replaced, no duplicate)", len(rows) == 3, str(rows))
    check("count label 2/3 · 2 done", dock._count_lbl.text() == "2/3 · 2 done", dock._count_lbl.text())
elif phase == "mid1":
    C.click_button(app, dock._next_btn)
    check("Next → item 2", H.wait_loaded(app, cell) and dock._index == 1)
    H.drag(app, canvas, H.pt(canvas, 0.3, 0.5), H.pt(canvas, 0.5, 0.5))
    C.click_button(app, dock._save_btn); st = C.wait_status(app, dock)
    check("item2 saved via Save button", st.startswith("Saved 1 file(s)"), st)
elif phase == "mid2":
    check("reopen: ○ ✓ ○", [t[0] for t in C.list_texts(dock)] == ["○", "✓", "○"], str(C.list_texts(dock)))
    check("reopen: first pending = item 1 (index 0)", dock._index == 0 and os.path.abspath(cell.series_data().meta.series_dir) == ws.items[0].path, str(dock._index))
    # Next from item 1 goes to item 2 (done) and not skipping it — observe
    C.click_button(app, dock._next_btn); H.wait_loaded(app, cell)
    check("Next steps to item 2 (done items are not skipped by Next)", dock._index == 1, str(dock._index))
elif phase == "nomanifest":
    check("manifest deleted → all ○ again, index 0", [t[0] for t in C.list_texts(dock)] == ["○", "○", "○"] and dock._index == 0, str(C.list_texts(dock)))
    check("png outputs in vidi_output are NOT scanned as items", len(ws.items) == 3 and all(it.path.endswith(".dcm") for it in ws.items), str([it.path for it in ws.items]))
sys.exit(C.finish(win, app))
