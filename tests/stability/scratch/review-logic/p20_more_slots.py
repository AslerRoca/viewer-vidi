"""More slot paths: Open directory with a cp1252 manifest (build_workspace→read_manifest), Open list on a UTF-16 csv,
unreadable .dcm item (chmod 000), tree-load into the active panel while the dock is open (tool not re-applied?)."""
from common import *
import subprocess, textwrap
d = fresh_ws("p20", [os.path.join(FIX, "bpd1_20100101_1.dcm"), os.path.join(FIX, "bpd1_20100101_2.dcm")])
out = os.path.join(d, "vidi_output"); os.makedirs(out)
with open(os.path.join(out, "manifest.csv"), "wb") as f:
    f.write("stem,source,saved_at,mask_pixels,x0,y0,x1,y1,formats,files\n".encode())
    f.write("other,/data/Röntgen/other.dcm,2026-10-26T10:00:00,10,,,,,png,png/other_mask.png\n".encode("cp1252"))
d2 = fresh_ws("p20b", [os.path.join(FIX, "bpd1_20100101_1.dcm")])
lst = os.path.join(SCR, "ws", "p20_list.csv")
with open(lst, "wb") as f: f.write("path\nbpd1_20100101_1.dcm\n".encode("utf-16"))
def run(label, body):
    child = textwrap.dedent(f"""
        import sys, os; sys.path.insert(0, {SCR!r})
        from common import *
        from PyQt5.QtWidgets import QFileDialog
        from PyQt5.QtCore import QTimer
        app, win = H.boot(); dock, quad = win._dock, win._quad
        win._ws_btn.setChecked(True); app.processEvents()
        def go():
            seen = H.auto_close_dialogs(app, 300)
            {body}
            print("dialogs:", seen, flush=True); app.quit()
        QTimer.singleShot(0, go); app.exec_(); print("CHILD_EXIT_OK", flush=True)
    """)
    r = subprocess.run([H.PYTHON, "-c", child], capture_output=True, text=True, timeout=120, cwd=SCR)
    err = "\n".join(l for l in r.stderr.splitlines() if "propagateSizeHints" not in l and "XDG_SESSION_TYPE" not in l)
    print(f"--- {label}: rc {r.returncode}\n{r.stdout[-600:]}\nstderr: {err[-700:]}")
    check(f"{label}: no abort", r.returncode == 0 and "CHILD_EXIT_OK" in r.stdout, f"rc={r.returncode}")
    return r
run("Open directory… with cp1252 manifest.csv", f"QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: {d!r}); dock._open_dir_btn.click(); app.processEvents(); print('ws', dock.workspace() and len(dock.workspace().items))")
run("Open list… on a UTF-16 csv", f"QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ({lst!r}, '')); dock._open_list_btn.click(); app.processEvents(); print('ws', dock.workspace())")
# unreadable item
os.chmod(os.path.join(d2, "bpd1_20100101_1.dcm"), 0)
try:
    r = run("Item file unreadable (chmod 000)", f"ws = H.open_workspace(app, win, {d2!r}); H.pump(app, 1500); print('sd', quad.active_cell().series_data(), 'status', repr(dock._status_lbl.text()), 'lbl', quad.active_cell().canvas()._label if hasattr(quad.active_cell().canvas(), '_label') else ''); dock._save_btn.click(); app.processEvents(); print('save status', repr(dock._status_lbl.text()))")
finally:
    os.chmod(os.path.join(d2, "bpd1_20100101_1.dcm"), 0o644)
# tree-load while dock open
r = run("Tree load into active panel while dock open", f"ws = H.open_workspace(app, win, {d2!r}); from viewer_vidi.tree_panel import _make_series_meta; win._on_series_selected(_make_series_meta({os.path.join(FIX, 'bpd1_20100101_2.dcm')!r})); H.wait_loaded(app, quad.active_cell()); c = quad.active_cell().canvas(); print('TOOLBTN', [m for m,b in dock._tool_btns.items() if b.isChecked()], 'CANVASMODE', c.wl_mode())")
check("after tree load with dock open, canvas mode still matches the checked tool (paint)", "CANVASMODE paint" in r.stdout, [l for l in r.stdout.splitlines() if "CANVASMODE" in l])
sys.exit(summary())
