"""Flow 9: error paths through the UI — unloadable .dcm items in the middle of a job,
read-only workspace (Export failed box), output dir name taken by a file."""
import os, sys, shutil, stat, time
import e2e_common as C
from e2e_common import check, H
from PyQt5.QtCore import Qt

app, win = H.boot()
dock, quad = win._dock, win._quad
C.click_button(app, win._ws_btn)
cell = quad.active_cell(); canvas = cell.canvas()

# ── 1. unloadable items ──
ERR = os.path.join(C.FX, "ws_err"); shutil.rmtree(os.path.join(ERR, "vidi_output"), ignore_errors=True)
seen = C.arm_dialog_closer(app)
C.open_dir_via_ui(app, win, ERR); ws = dock.workspace()
check("4 .dcm items incl. junk + truncated (accepted by name)", ws is not None and [it.stem for it in ws.items] == ["a_good", "b_junk", "c_trunc", "d_good"], str(ws and [it.stem for it in ws.items]))
check("item 1 loads", H.wait_loaded(app, cell))
C.click_button(app, dock._next_btn)
loaded = H.wait_loaded(app, cell, timeout=6.0)
check("junk item: never loads (no pixels), no crash", not loaded and dock._index == 1, f"loaded={loaded} sd={cell.series_data() is not None} px={canvas.displayed_pixels() is not None}")
print("   status after junk:", repr(dock._status_lbl.text()), "| series_lbl:", repr(cell._series_lbl.text()) if hasattr(cell, "_series_lbl") else "", "| dialogs:", seen)
check("mask cleared with the panel (invariants)", not H.invariants(canvas), str(H.invariants(canvas)))
C.ctrl_s(app, win, target=canvas); st = C.wait_status(app, dock)
check("Ctrl+S on an unloadable item: status (observe)", st == "Image still loading — try again in a moment." and not ws.items[1].done, st)
C.click_button(app, dock._next_btn)
loaded = H.wait_loaded(app, cell, timeout=6.0)
check("truncated item: never loads, no crash", not loaded and dock._index == 2, f"loaded={loaded}")
print("   status after trunc:", repr(dock._status_lbl.text()), "| dialogs:", seen)
C.click_button(app, dock._next_btn)
check("next good item loads after the broken ones", H.wait_loaded(app, cell) and dock._index == 3, str(dock._index))
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.5, 0.3))
C.ctrl_s(app, win, target=canvas); st = C.wait_status(app, dock)
check("saves fine", st.startswith("Saved 1 file(s)"), st)
C.click_button(app, dock._prev_btn); C.click_button(app, dock._prev_btn); H.pump(app, 300)
C.click_button(app, dock._prev_btn)
check("Prev ×3 across broken items back to item 1 loads", H.wait_loaded(app, cell) and dock._index == 0)
check("count 1/4 · 1 done", dock._count_lbl.text() == "1/4 · 1 done", dock._count_lbl.text())
check("no dialogs during broken-item navigation", seen == [], str(seen))

# ── 2. read-only workspace root → Export failed ──
RO = os.path.join(C.FX, "ws_ro"); shutil.rmtree(os.path.join(RO, "vidi_output"), ignore_errors=True)
os.chmod(RO, 0o555)
try:
    C.open_dir_via_ui(app, win, RO); wsr = dock.workspace()
    check("read-only ws opens, 1 item", wsr is not None and len(wsr.items) == 1 and H.wait_loaded(app, cell))
    H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.5, 0.3))
    seen = C.arm_dialog_closer(app)
    C.click_button(app, dock._save_btn); H.pump(app, 500)
    check("Save on read-only root → 'Export failed' box, item not done, nothing written", len(seen) == 1 and seen[0][1] == "Export failed" and not wsr.items[0].done and not os.path.exists(os.path.join(RO, "vidi_output")), str(seen))
    print("   export failed text:", seen and seen[0][2])
    check("status label untouched by the failure (observe)", dock._status_lbl.text() == "", repr(dock._status_lbl.text()))
finally:
    os.chmod(RO, 0o755)

# ── 3. output dir name already taken by a FILE ──
OF = os.path.join(C.FX, "ws_outfile")
C.open_dir_via_ui(app, win, OF); wso = dock.workspace()
check("ws with 'vidi_output' FILE opens, 1 item", wso is not None and len(wso.items) == 1 and H.wait_loaded(app, cell), str(wso and [it.stem for it in wso.items]))
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.5, 0.3))
seen = C.arm_dialog_closer(app)
C.click_button(app, dock._save_btn); H.pump(app, 500)
check("Save when out dir is a file → 'Export failed' box, not done", len(seen) == 1 and seen[0][1] == "Export failed" and not wso.items[0].done, str(seen))
check("the stray file is untouched", open(os.path.join(OF, "vidi_output")).read() == "not a dir\n")
sys.exit(C.finish(win, app))
